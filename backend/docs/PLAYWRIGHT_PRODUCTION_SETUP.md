# Playwright Production Installation Guide

This guide covers how to install Playwright browsers in production environments.

## Overview

Playwright requires two steps:
1. **Python package**: Installed via `pip install playwright` (already in requirements.txt)
2. **Browser binaries**: Installed separately via `playwright install chromium`

Browser binaries are ~170MB and must be installed after the Python package.

---

## 🐳 Docker/Container Environments

### Dockerfile (Already Updated)

The `Dockerfile` has been updated to automatically install Playwright browsers during the build:

```dockerfile
# System dependencies for Playwright (already added)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # ... other deps ...
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    # ... more Playwright deps ...

# Install Playwright browsers
RUN python -m playwright install chromium
```

### Building Docker Image

When building your Docker image, Playwright browsers will be automatically installed:

```bash
cd backend
docker build -t purchase-tracker-backend:latest .
```

**Build time**: Adds ~2-3 minutes to build time (downloading Chromium)

**Image size**: Adds ~200MB to final image size

### Verifying Installation in Container

After building, verify Playwright is installed:

```bash
# Build and run container
docker build -t purchase-tracker-backend:latest .
docker run --rm purchase-tracker-backend:latest python check_playwright.py
```

Expected output:
```
✅ Playwright package installed
✅ Playwright initialized successfully
✅ Chromium browser available
```

---

## 🖥️ Non-Docker Production Servers

### Option 1: Install During Deployment (Recommended)

Add to your deployment script:

```bash
#!/bin/bash
# deployment.sh

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies (includes playwright package)
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install chromium

# Verify installation
python check_playwright.py
```

### Option 2: Install Manually

SSH into your production server:

```bash
# Activate virtual environment
source /path/to/venv/bin/activate

# Install browsers
python -m playwright install chromium

# Verify
python check_playwright.py
```

### Option 3: Pre-install in Base Image/AMI

If using custom AMIs or base images:

1. Create a base image with Playwright pre-installed
2. Use that image for your application containers

---

## ☁️ AWS ECS / Fargate

### Current Setup (Dockerfile)

The Dockerfile is already configured. When you deploy:

```bash
./deploy.sh update
```

The build process will:
1. Install system dependencies
2. Install Python packages (including Playwright)
3. Install Chromium browser
4. Push to ECR
5. Deploy to ECS

### ECS Task Definition

No changes needed to your ECS task definition. The browsers are included in the Docker image.

### Resource Considerations

- **Memory**: Playwright browsers add ~50-100MB memory usage when running
- **CPU**: Minimal impact
- **Storage**: ~200MB per container image

---

## 🔄 CI/CD Pipelines

### GitHub Actions / GitLab CI

Add Playwright installation to your CI/CD pipeline:

```yaml
# .github/workflows/deploy.yml
- name: Install Playwright browsers
  run: |
    pip install playwright
    playwright install chromium
```

### Jenkins

Add to your Jenkinsfile:

```groovy
stage('Install Playwright') {
    steps {
        sh '''
            pip install playwright
            playwright install chromium
        '''
    }
}
```

---

## 🧪 Testing Installation

### Quick Test Script

Use the provided script:

```bash
python check_playwright.py
```

### Manual Test

```python
from playwright.sync_api import sync_playwright

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True)
page = browser.new_page()
page.goto("https://example.com")
print("✅ Playwright working!")
browser.close()
pw.stop()
```

---

## 🚨 Troubleshooting

### Issue: "Playwright browsers not installed"

**Solution:**
```bash
python -m playwright install chromium
```

### Issue: "Missing system dependencies"

**Solution:** Install required system libraries:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2

# Then install browsers
python -m playwright install chromium
```

### Issue: Docker build fails

**Check:**
1. System dependencies are installed in Dockerfile
2. Sufficient disk space in build context
3. Network connectivity during build

### Issue: Timeout during automation

**Check:**
1. Playwright browsers are installed: `python check_playwright.py`
2. Sufficient memory allocated to container/task
3. Check logs for specific error messages

---

## 📊 Production Checklist

- [ ] Dockerfile includes Playwright browser installation
- [ ] System dependencies are installed in Dockerfile
- [ ] Build process completes successfully
- [ ] `python check_playwright.py` passes in production
- [ ] Test "Process Inbound Creation" feature works
- [ ] Monitor memory usage (should be stable)
- [ ] Set up alerts for Playwright-related errors

---

## 🔒 Security Considerations

1. **Browser Sandbox**: Playwright runs browsers in sandboxed mode
2. **No External Network**: Browsers only access URLs you specify
3. **Resource Limits**: Set memory/CPU limits in ECS task definition
4. **Credentials**: Store PrepWorx credentials securely (use AWS Secrets Manager)

---

## 💡 Best Practices

1. **Install Only Chromium**: Don't install all browsers to save space
   ```bash
   playwright install chromium  # ✅ Good
   playwright install          # ❌ Installs all browsers (~500MB)
   ```

2. **Cache Browser Binaries**: In CI/CD, cache `~/.cache/ms-playwright` to speed up builds

3. **Monitor Resource Usage**: Track memory/CPU usage of automation tasks

4. **Error Handling**: The code includes timeout protection and error handling

5. **Logging**: All automation actions are logged for debugging

---

## 📝 Summary

**For Docker/ECS (Current Setup):**
- ✅ Already configured in Dockerfile
- ✅ No manual steps needed
- ✅ Just rebuild and deploy: `./deploy.sh update`

**For Non-Docker Production:**
- Add `python -m playwright install chromium` to deployment script
- Or run manually: `source venv/bin/activate && playwright install chromium`

**Verification:**
- Run `python check_playwright.py` to verify installation
- Test the "Process Inbound Creation" feature

---

## Questions?

If you encounter issues:
1. Check logs: `./deploy.sh logs`
2. Verify installation: `python check_playwright.py`
3. Check system dependencies are installed
4. Review error messages in application logs





