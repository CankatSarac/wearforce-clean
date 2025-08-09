package server

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"net"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/health"
	"google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"go.uber.org/zap"

	pb "github.com/wearforce/gateway/pkg/proto"
	"github.com/wearforce/gateway/internal/auth"
	"github.com/wearforce/gateway/internal/config"
)

// GRPCServer wraps the gRPC server with additional functionality
type GRPCServer struct {
	server       *grpc.Server
	listener     net.Listener
	config       *config.ServerConfig
	logger       *zap.Logger
	jwtValidator *auth.JWTValidator
	
	// Services
	audioService   *AudioStreamingService
	chatService    *ChatService
	gatewayService *GatewayService
	proxyService   *ServiceProxyService
}

// NewGRPCServer creates a new gRPC server
func NewGRPCServer(
	config *config.ServerConfig,
	tlsConfig *tls.Config,
	logger *zap.Logger,
	jwtValidator *auth.JWTValidator,
) (*GRPCServer, error) {
	
	// Create listener
	listener, err := net.Listen("tcp", fmt.Sprintf("%s:%d", config.Host, config.GRPCPort))
	if err != nil {
		return nil, fmt.Errorf("failed to listen on gRPC port: %w", err)
	}

	// Create gRPC server options
	opts := []grpc.ServerOption{
		grpc.UnaryInterceptor(grpc.ChainUnaryInterceptor(
			unaryAuthInterceptor(jwtValidator, logger),
			unaryLoggingInterceptor(logger),
			unaryPanicRecoveryInterceptor(logger),
		)),
		grpc.StreamInterceptor(grpc.ChainStreamInterceptor(
			streamAuthInterceptor(jwtValidator, logger),
			streamLoggingInterceptor(logger),
			streamPanicRecoveryInterceptor(logger),
		)),
		grpc.MaxRecvMsgSize(4 * 1024 * 1024), // 4MB
		grpc.MaxSendMsgSize(4 * 1024 * 1024), // 4MB
		grpc.ConnectionTimeout(30 * time.Second),
		grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
			MinTime:             30 * time.Second,
			PermitWithoutStream: true,
		}),
		grpc.KeepaliveParams(keepalive.ServerParameters{
			MaxConnectionIdle:     15 * time.Minute,
			MaxConnectionAge:      30 * time.Minute,
			MaxConnectionAgeGrace: 5 * time.Minute,
			Time:                  5 * time.Minute,
			Timeout:               1 * time.Minute,
		}),
	}

	// Add TLS credentials if configured
	if tlsConfig != nil {
		creds := credentials.NewTLS(tlsConfig)
		opts = append(opts, grpc.Creds(creds))
	}

	server := grpc.NewServer(opts...)

	// Create services
	audioService := &AudioStreamingService{logger: logger}
	chatService := &ChatService{logger: logger}
	gatewayService := &GatewayService{logger: logger}
	proxyService := &ServiceProxyService{logger: logger}

	// Register services
	pb.RegisterAudioStreamingServiceServer(server, audioService)
	pb.RegisterChatServiceServer(server, chatService)
	pb.RegisterGatewayServiceServer(server, gatewayService)
	pb.RegisterServiceProxyServiceServer(server, proxyService)

	// Register health service
	healthServer := health.NewServer()
	grpc_health_v1.RegisterHealthServer(server, healthServer)
	healthServer.SetServingStatus("", grpc_health_v1.HealthCheckResponse_SERVING)

	return &GRPCServer{
		server:         server,
		listener:       listener,
		config:         config,
		logger:         logger,
		jwtValidator:   jwtValidator,
		audioService:   audioService,
		chatService:    chatService,
		gatewayService: gatewayService,
		proxyService:   proxyService,
	}, nil
}

// Start starts the gRPC server
func (s *GRPCServer) Start() error {
	s.logger.Info("Starting gRPC server",
		zap.String("address", s.listener.Addr().String()),
	)

	if err := s.server.Serve(s.listener); err != nil {
		return fmt.Errorf("gRPC server failed: %w", err)
	}

	return nil
}

// Stop gracefully stops the gRPC server
func (s *GRPCServer) Stop(timeout time.Duration) error {
	s.logger.Info("Stopping gRPC server")

	done := make(chan struct{})
	go func() {
		s.server.GracefulStop()
		close(done)
	}()

	select {
	case <-done:
		s.logger.Info("gRPC server stopped gracefully")
		return nil
	case <-time.After(timeout):
		s.logger.Warn("gRPC server shutdown timeout, forcing stop")
		s.server.Stop()
		return nil
	}
}

// AudioStreamingService implements the audio streaming service
type AudioStreamingService struct {
	pb.UnimplementedAudioStreamingServiceServer
	logger *zap.Logger
	
	// Active streams
	streams sync.Map
}

// BiDirectionalStream handles bi-directional audio streaming
func (s *AudioStreamingService) BiDirectionalStream(stream pb.AudioStreamingService_BiDirectionalStreamServer) error {
	ctx := stream.Context()
	streamID := generateStreamID()
	
	s.logger.Info("Starting bi-directional audio stream", zap.String("stream_id", streamID))
	
	// Get user context from metadata
	user := getUserFromContext(ctx)
	if user == nil {
		return status.Error(codes.Unauthenticated, "authentication required")
	}

	// Create stream context
	streamCtx := &AudioStreamContext{
		StreamID: streamID,
		UserID:   user.UserID,
		StartTime: time.Now(),
	}
	
	s.streams.Store(streamID, streamCtx)
	defer s.streams.Delete(streamID)

	// Handle the stream
	errChan := make(chan error, 2)
	
	// Start receive goroutine
	go s.handleReceive(stream, streamCtx, errChan)
	
	// Start send goroutine (if needed for TTS responses)
	go s.handleSend(stream, streamCtx, errChan)

	// Wait for completion or error
	select {
	case err := <-errChan:
		if err != nil && err != io.EOF {
			s.logger.Error("Stream error",
				zap.String("stream_id", streamID),
				zap.Error(err),
			)
			return err
		}
	case <-ctx.Done():
		s.logger.Info("Stream cancelled",
			zap.String("stream_id", streamID),
			zap.Error(ctx.Err()),
		)
		return ctx.Err()
	}

	s.logger.Info("Bi-directional stream completed", zap.String("stream_id", streamID))
	return nil
}

// SpeechToText handles speech-to-text streaming
func (s *AudioStreamingService) SpeechToText(stream pb.AudioStreamingService_SpeechToTextServer) error {
	ctx := stream.Context()
	streamID := generateStreamID()
	
	s.logger.Info("Starting STT stream", zap.String("stream_id", streamID))
	
	for {
		req, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			s.logger.Error("STT stream receive error",
				zap.String("stream_id", streamID),
				zap.Error(err),
			)
			return err
		}

		// Process STT request
		resp, err := s.processSttRequest(ctx, req)
		if err != nil {
			s.logger.Error("STT processing error",
				zap.String("stream_id", streamID),
				zap.Error(err),
			)
			return err
		}

		if err := stream.Send(resp); err != nil {
			s.logger.Error("STT stream send error",
				zap.String("stream_id", streamID),
				zap.Error(err),
			)
			return err
		}
	}

	return nil
}

// TextToSpeech handles text-to-speech conversion
func (s *AudioStreamingService) TextToSpeech(req *pb.TtsRequest, stream pb.AudioStreamingService_TextToSpeechServer) error {
	ctx := stream.Context()
	streamID := generateStreamID()
	
	s.logger.Info("Starting TTS stream",
		zap.String("stream_id", streamID),
		zap.String("text", req.Text),
	)

	// Process TTS request and stream audio chunks
	audioChunks, err := s.processTtsRequest(ctx, req)
	if err != nil {
		return err
	}

	for _, chunk := range audioChunks {
		resp := &pb.TtsResponse{
			Response: &pb.TtsResponse_AudioData{
				AudioData: chunk,
			},
		}

		if err := stream.Send(resp); err != nil {
			s.logger.Error("TTS stream send error",
				zap.String("stream_id", streamID),
				zap.Error(err),
			)
			return err
		}
	}

	return nil
}

// GetAudioConfig returns supported audio configurations
func (s *AudioStreamingService) GetAudioConfig(ctx context.Context, req *pb.AudioConfigRequest) (*pb.AudioConfigResponse, error) {
	s.logger.Debug("Audio config requested",
		zap.String("device_type", req.DeviceType),
		zap.String("platform", req.Platform),
	)

	// Return supported configurations
	resp := &pb.AudioConfigResponse{
		SupportedConfigs: []*pb.AudioConfig{
			{
				Encoding:                   pb.AudioConfig_LINEAR16,
				SampleRateHertz:            16000,
				AudioChannelCount:          1,
				LanguageCode:              "en-US",
				EnableWordTimeOffsets:     true,
				EnableAutomaticPunctuation: true,
			},
			{
				Encoding:                   pb.AudioConfig_WEBM_OPUS,
				SampleRateHertz:            48000,
				AudioChannelCount:          1,
				LanguageCode:              "en-US",
				EnableWordTimeOffsets:     true,
				EnableAutomaticPunctuation: true,
			},
		},
		SupportedVoices: []*pb.VoiceConfig{
			{
				VoiceName:    "en-US-Standard-A",
				LanguageCode: "en-US",
				Gender:       pb.VoiceConfig_FEMALE,
				SpeakingRate: 1.0,
				Pitch:        0.0,
			},
			{
				VoiceName:    "en-US-Standard-B",
				LanguageCode: "en-US",
				Gender:       pb.VoiceConfig_MALE,
				SpeakingRate: 1.0,
				Pitch:        0.0,
			},
		},
		SupportedLanguages: []string{"en-US", "es-ES", "fr-FR", "de-DE"},
	}

	return resp, nil
}

// AudioStreamContext holds context for an active audio stream
type AudioStreamContext struct {
	StreamID  string
	UserID    string
	StartTime time.Time
}

// handleReceive handles receiving audio data from client
func (s *AudioStreamingService) handleReceive(
	stream pb.AudioStreamingService_BiDirectionalStreamServer,
	streamCtx *AudioStreamContext,
	errChan chan error,
) {
	for {
		req, err := stream.Recv()
		if err == io.EOF {
			errChan <- nil
			return
		}
		if err != nil {
			errChan <- err
			return
		}

		// Process the request based on type
		switch req.Request.(type) {
		case *pb.AudioRequest_Config:
			s.logger.Debug("Received audio config", zap.String("stream_id", streamCtx.StreamID))
		case *pb.AudioRequest_AudioData:
			s.logger.Debug("Received audio data",
				zap.String("stream_id", streamCtx.StreamID),
				zap.Int("size", len(req.GetAudioData().Content)),
			)
			// Process audio data for STT
			if err := s.processAudioData(streamCtx, req.GetAudioData()); err != nil {
				errChan <- err
				return
			}
		case *pb.AudioRequest_TextData:
			s.logger.Debug("Received text data", zap.String("stream_id", streamCtx.StreamID))
			// Process text data for TTS
			if err := s.processTextData(streamCtx, req.GetTextData()); err != nil {
				errChan <- err
				return
			}
		case *pb.AudioRequest_Control:
			s.logger.Debug("Received control message", zap.String("stream_id", streamCtx.StreamID))
			// Handle control messages
			if err := s.processControlMessage(streamCtx, req.GetControl()); err != nil {
				errChan <- err
				return
			}
		}
	}
}

// handleSend handles sending responses to client
func (s *AudioStreamingService) handleSend(
	stream pb.AudioStreamingService_BiDirectionalStreamServer,
	streamCtx *AudioStreamContext,
	errChan chan error,
) {
	// This would handle sending TTS audio or STT transcriptions
	// Implementation depends on your specific requirements
	select {
	case <-stream.Context().Done():
		return
	}
}

// Helper methods for processing different types of data
func (s *AudioStreamingService) processAudioData(ctx *AudioStreamContext, data *pb.AudioData) error {
	// Forward to STT service
	s.logger.Debug("Processing audio data",
		zap.String("stream_id", ctx.StreamID),
		zap.Int("size", len(data.Content)),
	)
	return nil
}

func (s *AudioStreamingService) processTextData(ctx *AudioStreamContext, data *pb.TextData) error {
	// Forward to TTS service
	s.logger.Debug("Processing text data",
		zap.String("stream_id", ctx.StreamID),
		zap.String("text", data.Content),
	)
	return nil
}

func (s *AudioStreamingService) processControlMessage(ctx *AudioStreamContext, control *pb.ControlMessage) error {
	s.logger.Debug("Processing control message",
		zap.String("stream_id", ctx.StreamID),
		zap.String("command", control.Command.String()),
	)
	return nil
}

func (s *AudioStreamingService) processSttRequest(ctx context.Context, req *pb.SttRequest) (*pb.SttResponse, error) {
	// Placeholder for STT processing
	return &pb.SttResponse{
		Response: &pb.SttResponse_Transcription{
			Transcription: &pb.TranscriptionResult{
				Alternatives: []*pb.TranscriptAlternative{
					{
						Transcript: "Sample transcription",
						Confidence: 0.95,
					},
				},
				IsFinal:    true,
				Stability:  0.9,
			},
		},
	}, nil
}

func (s *AudioStreamingService) processTtsRequest(ctx context.Context, req *pb.TtsRequest) ([]*pb.AudioData, error) {
	// Placeholder for TTS processing
	return []*pb.AudioData{
		{
			Content: []byte("dummy audio data"),
		},
	}, nil
}

// Utility functions
func generateStreamID() string {
	return fmt.Sprintf("stream-%d", time.Now().UnixNano())
}

func getUserFromContext(ctx context.Context) *auth.UserContext {
	if md, ok := metadata.FromIncomingContext(ctx); ok {
		if userID := md.Get("user-id"); len(userID) > 0 {
			return &auth.UserContext{
				UserID: userID[0],
			}
		}
	}
	return nil
}