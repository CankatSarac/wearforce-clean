package tracing

import (
	"context"
	"fmt"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	"go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	oteltrace "go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/config"
)

// TracingManager manages OpenTelemetry tracing
type TracingManager struct {
	tracer   oteltrace.Tracer
	provider *trace.TracerProvider
	config   *config.TracingConfig
	logger   *zap.Logger
}

// NewTracingManager creates a new tracing manager
func NewTracingManager(config *config.TracingConfig, logger *zap.Logger) (*TracingManager, error) {
	if !config.Enabled {
		return &TracingManager{
			tracer: otel.Tracer("noop"),
			config: config,
			logger: logger,
		}, nil
	}

	// Create resource
	res, err := newResource(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}

	// Create exporter
	exporter, err := newExporter(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create exporter: %w", err)
	}

	// Create sampler
	sampler := newSampler(config.Sampling)

	// Create tracer provider
	provider := trace.NewTracerProvider(
		trace.WithBatcher(exporter),
		trace.WithResource(res),
		trace.WithSampler(sampler),
	)

	// Set global tracer provider
	otel.SetTracerProvider(provider)

	// Set global text map propagator
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	// Get tracer
	tracer := otel.Tracer(config.ServiceName)

	logger.Info("Tracing initialized",
		zap.String("service", config.ServiceName),
		zap.String("version", config.ServiceVersion),
		zap.String("exporter", config.Exporter.Type),
		zap.String("endpoint", config.Exporter.Endpoint),
	)

	return &TracingManager{
		tracer:   tracer,
		provider: provider,
		config:   config,
		logger:   logger,
	}, nil
}

// GetTracer returns the configured tracer
func (tm *TracingManager) GetTracer() oteltrace.Tracer {
	return tm.tracer
}

// Shutdown gracefully shuts down the tracing provider
func (tm *TracingManager) Shutdown(ctx context.Context) error {
	if tm.provider == nil {
		return nil
	}

	tm.logger.Info("Shutting down tracing provider")
	return tm.provider.Shutdown(ctx)
}

// newResource creates a new OpenTelemetry resource
func newResource(config *config.TracingConfig) (*resource.Resource, error) {
	attributes := []attribute.KeyValue{
		semconv.ServiceNameKey.String(config.ServiceName),
		semconv.ServiceVersionKey.String(config.ServiceVersion),
		semconv.DeploymentEnvironmentKey.String(config.Environment),
	}

	// Add custom resource attributes
	for key, value := range config.Resources {
		attributes = append(attributes, attribute.String(key, value))
	}

	return resource.Merge(
		resource.Default(),
		resource.NewWithAttributes(
			semconv.SchemaURL,
			attributes...,
		),
	)
}

// newExporter creates a new trace exporter based on configuration
func newExporter(config *config.TracingConfig) (trace.SpanExporter, error) {
	switch config.Exporter.Type {
	case "otlp-grpc":
		return newOTLPGRPCExporter(config.Exporter)
	case "otlp-http":
		return newOTLPHTTPExporter(config.Exporter)
	case "jaeger":
		return newJaegerExporter(config.Exporter)
	default:
		return nil, fmt.Errorf("unsupported exporter type: %s", config.Exporter.Type)
	}
}

// newOTLPGRPCExporter creates OTLP gRPC exporter
func newOTLPGRPCExporter(config config.ExporterConfig) (trace.SpanExporter, error) {
	opts := []otlptracegrpc.Option{
		otlptracegrpc.WithEndpoint(config.Endpoint),
	}

	if config.Insecure {
		opts = append(opts, otlptracegrpc.WithInsecure())
	}

	if len(config.Headers) > 0 {
		opts = append(opts, otlptracegrpc.WithHeaders(config.Headers))
	}

	client := otlptracegrpc.NewClient(opts...)
	return otlptrace.New(context.Background(), client)
}

// newOTLPHTTPExporter creates OTLP HTTP exporter
func newOTLPHTTPExporter(config config.ExporterConfig) (trace.SpanExporter, error) {
	opts := []otlptracehttp.Option{
		otlptracehttp.WithEndpoint(config.Endpoint),
	}

	if config.Insecure {
		opts = append(opts, otlptracehttp.WithInsecure())
	}

	if len(config.Headers) > 0 {
		opts = append(opts, otlptracehttp.WithHeaders(config.Headers))
	}

	client := otlptracehttp.NewClient(opts...)
	return otlptrace.New(context.Background(), client)
}

// newJaegerExporter creates Jaeger exporter (deprecated but still used)
func newJaegerExporter(config config.ExporterConfig) (trace.SpanExporter, error) {
	// Note: Jaeger exporter is deprecated in favor of OTLP
	// This is a placeholder - you should use OTLP exporters
	return nil, fmt.Errorf("jaeger exporter is deprecated, use otlp-http or otlp-grpc")
}

// newSampler creates a new sampler based on configuration
func newSampler(config config.SamplingConfig) trace.Sampler {
	switch config.Type {
	case "always":
		return trace.AlwaysSample()
	case "never":
		return trace.NeverSample()
	case "ratio":
		return trace.TraceIDRatioBased(config.Ratio)
	default:
		return trace.TraceIDRatioBased(0.1) // Default 10% sampling
	}
}

// StartSpan starts a new span with common attributes
func (tm *TracingManager) StartSpan(ctx context.Context, name string, opts ...oteltrace.SpanStartOption) (context.Context, oteltrace.Span) {
	return tm.tracer.Start(ctx, name, opts...)
}

// AddEvent adds an event to the current span
func AddEvent(span oteltrace.Span, name string, attributes ...attribute.KeyValue) {
	span.AddEvent(name, oteltrace.WithAttributes(attributes...))
}

// SetError sets error information on the span
func SetError(span oteltrace.Span, err error) {
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, err.Error())
	}
}

// SetHTTPAttributes sets HTTP-related attributes on the span
func SetHTTPAttributes(span oteltrace.Span, method, url, userAgent string, statusCode int) {
	span.SetAttributes(
		semconv.HTTPMethodKey.String(method),
		semconv.HTTPURLKey.String(url),
		semconv.HTTPUserAgentKey.String(userAgent),
		semconv.HTTPStatusCodeKey.Int(statusCode),
	)
}

// SetDatabaseAttributes sets database-related attributes on the span
func SetDatabaseAttributes(span oteltrace.Span, system, name, operation string) {
	span.SetAttributes(
		semconv.DBSystemKey.String(system),
		semconv.DBNameKey.String(name),
		semconv.DBOperationKey.String(operation),
	)
}

// SetGRPCAttributes sets gRPC-related attributes on the span
func SetGRPCAttributes(span oteltrace.Span, service, method string, statusCode int) {
	span.SetAttributes(
		semconv.RPCSystemKey.String("grpc"),
		semconv.RPCServiceKey.String(service),
		semconv.RPCMethodKey.String(method),
		semconv.RPCGRPCStatusCodeKey.Int(statusCode),
	)
}

// SetUserAttributes sets user-related attributes on the span
func SetUserAttributes(span oteltrace.Span, userID, email string, roles []string) {
	span.SetAttributes(
		attribute.String("user.id", userID),
		attribute.String("user.email", email),
		attribute.StringSlice("user.roles", roles),
	)
}

// TraceableFunc is a helper to trace function calls
func (tm *TracingManager) TraceableFunc(ctx context.Context, name string, fn func(ctx context.Context, span oteltrace.Span) error) error {
	ctx, span := tm.StartSpan(ctx, name)
	defer span.End()

	err := fn(ctx, span)
	if err != nil {
		SetError(span, err)
	}

	return err
}

// TraceableFuncWithResult is a helper to trace function calls that return a result
func (tm *TracingManager) TraceableFuncWithResult[T any](ctx context.Context, name string, fn func(ctx context.Context, span oteltrace.Span) (T, error)) (T, error) {
	ctx, span := tm.StartSpan(ctx, name)
	defer span.End()

	result, err := fn(ctx, span)
	if err != nil {
		SetError(span, err)
	}

	return result, err
}

// GetTraceID extracts trace ID from context
func GetTraceID(ctx context.Context) string {
	spanCtx := oteltrace.SpanContextFromContext(ctx)
	if spanCtx.HasTraceID() {
		return spanCtx.TraceID().String()
	}
	return ""
}

// GetSpanID extracts span ID from context
func GetSpanID(ctx context.Context) string {
	spanCtx := oteltrace.SpanContextFromContext(ctx)
	if spanCtx.HasSpanID() {
		return spanCtx.SpanID().String()
	}
	return ""
}

// InjectHTTPHeaders injects tracing headers into HTTP request
func InjectHTTPHeaders(ctx context.Context, headers map[string]string) {
	carrier := propagation.MapCarrier(headers)
	otel.GetTextMapPropagator().Inject(ctx, carrier)
}

// ExtractHTTPHeaders extracts tracing context from HTTP headers
func ExtractHTTPHeaders(ctx context.Context, headers map[string]string) context.Context {
	carrier := propagation.MapCarrier(headers)
	return otel.GetTextMapPropagator().Extract(ctx, carrier)
}

// Custom span options for different scenarios
func WithHTTPServerSpanOptions(method, route string) oteltrace.SpanStartOption {
	return oteltrace.WithSpanKind(oteltrace.SpanKindServer),
		oteltrace.WithAttributes(
			semconv.HTTPMethodKey.String(method),
			semconv.HTTPRouteKey.String(route),
		)
}

func WithHTTPClientSpanOptions(method, url string) oteltrace.SpanStartOption {
	return oteltrace.WithSpanKind(oteltrace.SpanKindClient),
		oteltrace.WithAttributes(
			semconv.HTTPMethodKey.String(method),
			semconv.HTTPURLKey.String(url),
		)
}

func WithDatabaseSpanOptions(system, operation string) oteltrace.SpanStartOption {
	return oteltrace.WithSpanKind(oteltrace.SpanKindClient),
		oteltrace.WithAttributes(
			semconv.DBSystemKey.String(system),
			semconv.DBOperationKey.String(operation),
		)
}

func WithGRPCServerSpanOptions(service, method string) oteltrace.SpanStartOption {
	return oteltrace.WithSpanKind(oteltrace.SpanKindServer),
		oteltrace.WithAttributes(
			semconv.RPCSystemKey.String("grpc"),
			semconv.RPCServiceKey.String(service),
			semconv.RPCMethodKey.String(method),
		)
}

func WithGRPCClientSpanOptions(service, method string) oteltrace.SpanStartOption {
	return oteltrace.WithSpanKind(oteltrace.SpanKindClient),
		oteltrace.WithAttributes(
			semconv.RPCSystemKey.String("grpc"),
			semconv.RPCServiceKey.String(service),
			semconv.RPCMethodKey.String(method),
		)
}