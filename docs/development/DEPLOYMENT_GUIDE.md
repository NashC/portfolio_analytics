# Portfolio Analytics Dashboard - Deployment Guide

## 🚀 Quick Start

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the enhanced dashboard
streamlit run ui/streamlit_app_v2.py --server.port 8502

# Run performance benchmark
python scripts/simple_benchmark.py

# Run feature demo
python scripts/demo_dashboard.py
```

### Production Deployment

#### Option 1: Streamlit Cloud
1. Push code to GitHub repository
2. Connect to Streamlit Cloud
3. Deploy from `ui/streamlit_app_v2.py`
4. Configure secrets for any API keys

#### Option 2: Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8501

CMD ["streamlit", "run", "ui/streamlit_app_v2.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

#### Option 3: Cloud Platforms
- **Heroku**: Use `setup.sh` and `Procfile`
- **AWS EC2**: Deploy with nginx reverse proxy
- **Google Cloud Run**: Containerized deployment
- **Azure Container Instances**: Quick container deployment

## 🔧 Configuration

### Environment Variables
```bash
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

### Performance Tuning
- Enable caching with Redis for production
- Use CDN for static assets
- Implement load balancing for high traffic
- Monitor memory usage and optimize queries

## 📊 Monitoring

### Key Metrics to Monitor
- Dashboard load time (target: <2s)
- Memory usage (target: <500MB)
- Error rates (target: <1%)
- User session duration
- Feature usage analytics

### Health Checks
```python
# Add to your monitoring system
def health_check():
    try:
        # Test data loading
        transactions = load_transactions()
        if transactions is None or transactions.empty:
            return False
        
        # Test calculations
        metrics = compute_portfolio_metrics(transactions)
        if 'error' in metrics:
            return False
        
        return True
    except Exception:
        return False
```

## 🔒 Security Considerations

### Data Protection
- Never commit sensitive data to version control
- Use environment variables for API keys
- Implement proper input validation
- Regular security updates

### Access Control
- Consider authentication for production use
- Implement role-based access if needed
- Use HTTPS in production
- Regular backup of portfolio data

## 📈 Scaling Considerations

### Performance Optimization
- Implement database connection pooling
- Use async operations for heavy computations
- Consider microservices architecture for large scale
- Implement proper error handling and retry logic

### Data Management
- Regular data cleanup and archiving
- Implement data validation pipelines
- Consider data partitioning for large datasets
- Backup and disaster recovery procedures
