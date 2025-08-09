# WearForce-Clean LLM Inference Service

A high-performance, production-ready LLM inference service built with vLLM, featuring OpenAI-compatible APIs, function calling, batch processing, and comprehensive monitoring.

## 🚀 Features

### Core Capabilities
- **Multi-Model Support**: gpt-oss-20b and gpt-oss-120b models
- **OpenAI Compatibility**: Drop-in replacement for OpenAI API
- **Function Calling**: LangGraph-compatible tool integration
- **Streaming Support**: Real-time response streaming
- **Batch Processing**: Efficient request batching with load balancing
- **Token Usage Tracking**: Comprehensive billing and usage analytics

### Performance & Reliability
- **vLLM Backend**: High-throughput inference with optimizations
- **Auto-scaling**: Dynamic model loading and memory management
- **Load Balancing**: Intelligent request distribution
- **Error Handling**: Comprehensive retry logic and error recovery
- **Health Monitoring**: Detailed health checks and metrics

### Deployment Flexibility
- **Cloud & Edge**: Optimized configurations for both deployments
- **GPU Support**: CUDA optimization with memory management
- **Docker Ready**: Complete containerization with GPU support
- **Monitoring Stack**: Prometheus, Grafana integration

## 📋 Requirements

### Minimum Requirements (Edge Deployment)
- **GPU**: 16GB VRAM (RTX 4090, A6000, etc.)
- **RAM**: 32GB system memory
- **Storage**: 100GB for models and cache
- **CUDA**: 12.1+ with compatible drivers

### Recommended Requirements (Cloud Deployment)
- **GPU**: 80GB VRAM (A100 80GB)
- **RAM**: 128GB system memory
- **Storage**: 500GB SSD for models and cache
- **Network**: High-bandwidth for model downloads

### Software Requirements
- Docker 20.10+
- Docker Compose 2.0+
- NVIDIA Docker runtime
- CUDA 12.1+

## 🛠 Installation

### Quick Start

1. **Clone and navigate to the service**:
   ```bash
   cd gateway/ai-services/llm-service
   ```

2. **Configure deployment type**:
   ```bash
   # For edge deployment (16GB GPU)
   export DEPLOYMENT_TYPE=edge
   
   # For cloud deployment (80GB GPU)
   export DEPLOYMENT_TYPE=cloud
   ```

3. **Deploy with the automated script**:
   ```bash
   ./deploy.sh
   ```

### Manual Deployment

1. **Copy environment configuration**:
   ```bash
   cp .env.example .env
   ```

2. **Edit configuration** (optional):
   ```bash
   nano .env
   ```

3. **Build and start services**:
   ```bash
   docker-compose up -d
   ```

4. **Verify deployment**:
   ```bash
   curl http://localhost:8004/health
   ```

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Deployment Configuration
DEPLOYMENT_TYPE=edge          # "edge" or "cloud"
SERVICE_NAME=llm-service
PORT=8004

# Model Paths
GPT_OSS_20B_PATH=/app/models/gpt-oss-20b
GPT_OSS_120B_PATH=/app/models/gpt-oss-120b

# vLLM Configuration
TENSOR_PARALLEL_SIZE=1        # GPU parallelization
MAX_NUM_SEQS=128             # Batch size
LLM_GPU_MEMORY=0.75          # GPU memory utilization

# Performance Tuning
BATCH_SIZE=32                 # Request batching
BATCH_TIMEOUT=0.1            # Batch timeout (seconds)
```

### Deployment Types

#### Edge Deployment (16GB GPU)
- Optimized for single GPU setups
- Memory-efficient configurations
- Quantization support for smaller models
- Lower batch sizes for stability

#### Cloud Deployment (80GB A100)
- Multi-GPU tensor parallelism
- Maximum performance configurations
- Large batch processing
- Higher memory utilization

## 📝 API Usage

### Chat Completions (OpenAI Compatible)

```python
import openai

client = openai.OpenAI(
    api_key="not-needed",
    base_url="http://localhost:8004/v1"
)

response = client.chat.completions.create(
    model="gpt-oss-20b",
    messages=[
        {"role": "user", "content": "Hello, how are you?"}
    ]
)
```

### Streaming Responses

```python
stream = client.chat.completions.create(
    model="gpt-oss-20b",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
```

### Function Calling

```python
functions = [
    {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            }
        }
    }
]

response = client.chat.completions.create(
    model="gpt-oss-20b",
    messages=[{"role": "user", "content": "What's the weather in Paris?"}],
    functions=functions,
    function_call="auto"
)
```

### Batch Processing

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8004/batch",
        json=[
            {"model": "gpt-oss-20b", "prompt": "Hello"},
            {"model": "gpt-oss-20b", "prompt": "How are you?"}
        ]
    )
    batch_id = response.json()["id"]
```

## 📊 Monitoring

### Health Checks

```bash
# Basic health check
curl http://localhost:8004/health

# Detailed statistics
curl http://localhost:8004/stats

# Model-specific stats
curl http://localhost:8004/stats/models
```

### Metrics & Monitoring

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Service Metrics**: http://localhost:8000/metrics

### Key Metrics

- Request throughput and latency
- GPU memory utilization
- Model loading times
- Error rates and types
- Token usage and billing

## 🔧 Administration

### Model Management

```bash
# Reload a specific model
curl -X POST http://localhost:8004/admin/reload/gpt-oss-20b

# List available models
curl http://localhost:8004/models

# Get function calling stats
curl http://localhost:8004/v1/functions/stats
```

### Logs and Debugging

```bash
# View service logs
docker-compose logs -f llm-service

# Check GPU usage
docker exec llm-service nvidia-smi

# Monitor resource usage
docker stats llm-service
```

## 🏗 Architecture

### Service Components

1. **Engine Manager**: Multi-model loading and management
2. **Batch Processor**: Request batching with load balancing  
3. **Function Processor**: Tool calling and function execution
4. **Billing Tracker**: Token usage and cost tracking
5. **Health Monitor**: Comprehensive service monitoring

### Request Flow

```
Client Request → Load Balancer → Batch Processor → vLLM Engine → Response
                      ↓
                Function Processor (if functions present)
                      ↓
                Billing Tracker → Usage Analytics
```

### Performance Optimizations

- **Prefix Caching**: Efficient prompt reuse
- **Flash Attention**: Memory-efficient attention
- **Quantization**: Model compression for edge deployment
- **Dynamic Batching**: Optimal request grouping
- **Memory Management**: Automatic cleanup and optimization

## 🚨 Troubleshooting

### Common Issues

#### Out of Memory Errors
```bash
# Reduce memory usage
export LLM_GPU_MEMORY=0.6
export MAX_NUM_SEQS=64

# Clear GPU cache
docker exec llm-service python -c "import torch; torch.cuda.empty_cache()"
```

#### Model Loading Failures
```bash
# Check model paths
docker exec llm-service ls -la /app/models/

# Verify model permissions
docker exec llm-service python -c "import os; print(os.path.exists('/app/models/gpt-oss-20b'))"
```

#### Service Won't Start
```bash
# Check logs
docker-compose logs llm-service

# Verify GPU access
docker run --rm --gpus all nvidia/cuda:12.1-base nvidia-smi
```

### Performance Issues

#### Slow Response Times
1. Check GPU utilization: `nvidia-smi`
2. Increase batch size: `BATCH_SIZE=64`
3. Reduce model precision: Enable quantization
4. Scale horizontally: Add more GPU instances

#### High Memory Usage
1. Reduce GPU memory utilization: `LLM_GPU_MEMORY=0.7`
2. Lower batch size: `MAX_NUM_SEQS=64`
3. Enable swap space: `SWAP_SPACE=8`
4. Use model quantization for edge deployment

## 🔐 Security Considerations

- API key authentication (configure as needed)
- Rate limiting (60 requests/minute default)
- Input validation and sanitization
- Function calling sandboxing
- Network security with Docker networks

## 📈 Scaling

### Horizontal Scaling
- Deploy multiple service instances
- Use load balancer (nginx, HAProxy)
- Share Redis and PostgreSQL instances
- Implement sticky sessions for streaming

### Vertical Scaling
- Increase GPU memory allocation
- Add more GPUs with tensor parallelism
- Optimize batch sizes and parameters
- Use faster storage (NVMe SSDs)

## 🧪 Testing

### Load Testing

```python
import asyncio
import httpx
import time

async def load_test():
    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(100):
            task = client.post(
                "http://localhost:8004/v1/chat/completions",
                json={
                    "model": "gpt-oss-20b",
                    "messages": [{"role": "user", "content": f"Test {i}"}]
                }
            )
            tasks.append(task)
        
        start_time = time.time()
        responses = await asyncio.gather(*tasks)
        end_time = time.time()
        
        print(f"Completed 100 requests in {end_time - start_time:.2f} seconds")
        print(f"Average response time: {(end_time - start_time) / 100:.3f} seconds")

asyncio.run(load_test())
```

## 📄 License

This project is part of the WearForce-Clean AI Services suite. See the main project for licensing information.

## 🤝 Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Ensure all health checks pass
5. Test both edge and cloud deployments

## 📞 Support

For issues and support:
1. Check the troubleshooting section
2. Review service logs: `docker-compose logs llm-service`
3. Monitor health endpoint: `curl http://localhost:8004/health`
4. Check GPU status: `nvidia-smi`