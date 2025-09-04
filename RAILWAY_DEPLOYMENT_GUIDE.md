# 🚀 iBeekeeper Railway Deployment Guide

## Prerequisites
- GitHub account with your iBeekeeper repository
- Railway.app account (free tier available)
- Your repository should be committed and pushed to GitHub

## Step-by-Step Deployment Process

### 1. Prepare Your Repository
Ensure these files are in your repository root:

✅ **Already Configured:**
- `Procfile` - ✅ Updated for Flask app factory
- `requirements.txt` - ✅ All dependencies included
- `app.py` - ✅ Flask app with create_app() factory
- `config.py` - ✅ Environment-aware configuration

### 2. Deploy to Railway

#### Option A: Deploy from GitHub (Recommended)

1. **Visit Railway.app**
   - Go to https://railway.app
   - Click "Start a New Project"
   - Sign in with your GitHub account

2. **Connect Your Repository**
   - Click "Deploy from GitHub repo"
   - Select your iBeekeeper repository
   - Railway will automatically detect it's a Python app

3. **Configure Environment Variables**
   Click on your deployed service → Variables tab and add:

   ```bash
   # Required Variables
   FLASK_ENV=production
   SECRET_KEY=your-64-character-secure-key-here
   
   # Database (Railway provides PostgreSQL)
   DATABASE_URL=postgresql://user:pass@host:port/db
   
   # Session Security
   SESSION_COOKIE_SECURE=True
   
   # File Uploads
   UPLOAD_FOLDER=/app/uploads
   
   # Optional - Wise API
   WISE_API_URL=https://api.wise.com
   ```

4. **Generate Secure Secret Key**
   ```python
   # Run this locally to generate a key:
   import secrets
   print(secrets.token_hex(32))
   ```

#### Option B: Deploy via Railway CLI

1. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   # or
   brew install railway
   ```

2. **Login and Deploy**
   ```bash
   railway login
   railway init
   railway up
   ```

### 3. Database Setup

Railway automatically provisions a PostgreSQL database. Your app will:
- ✅ Auto-create tables on first run (via SQLAlchemy)
- ✅ Handle database migrations automatically
- ✅ Use environment DATABASE_URL

### 4. Domain & SSL

Railway automatically provides:
- ✅ Free HTTPS subdomain (yourapp.railway.app)
- ✅ SSL certificate
- ✅ Custom domain support (paid plans)

### 5. Verify Deployment

1. **Check Logs**
   - Railway Dashboard → Your Project → View Logs
   - Look for successful Flask app startup

2. **Test the Application**
   - Visit your Railway URL
   - Register a new account or login with existing
   - Test file uploads and core functionality

3. **Create Admin User** (if needed)
   Use Railway's console feature or add this to your app startup.

### 6. Production Configuration Verification

#### Environment Variables Checklist:
```bash
✅ FLASK_ENV=production
✅ SECRET_KEY=64-character-hex-key
✅ DATABASE_URL=postgresql://... (auto-provided by Railway)
✅ SESSION_COOKIE_SECURE=True
✅ UPLOAD_FOLDER=/app/uploads
```

#### Security Headers Verification:
Your app already includes:
- ✅ CSRF Protection
- ✅ Security Headers (CSP, X-Frame-Options, etc.)
- ✅ XSS Protection
- ✅ SQL Injection Prevention

## Railway-Specific Features

### Auto Scaling
- Railway automatically scales your app based on traffic
- Free tier includes reasonable limits for small applications

### Database Backups
- Railway PostgreSQL includes automatic backups
- Available in project dashboard

### Monitoring
- Built-in monitoring and alerting
- View metrics in Railway dashboard

### Custom Domains
- Add custom domain in project settings
- Automatic SSL certificate generation

## Cost Estimation

**Free Tier Limits:**
- $5/month in usage credits
- 500 hours of runtime
- 1GB RAM, 1 vCPU
- 1GB database storage

**Typical Monthly Cost for Small App:**
- $0 - $20 depending on usage
- Database scales with storage needs

## Troubleshooting Common Issues

### 1. App Won't Start
**Check logs for:**
```bash
# Missing environment variables
KeyError: 'SECRET_KEY'

# Database connection issues  
sqlalchemy.exc.OperationalError

# Import errors
ModuleNotFoundError: No module named 'flask'
```

**Solutions:**
- Verify all environment variables are set
- Check requirements.txt includes all dependencies
- Ensure Procfile uses correct app factory syntax

### 2. File Upload Issues
```bash
# Create uploads directory in your app startup
import os
os.makedirs('/app/uploads/users', exist_ok=True)
```

### 3. Database Migrations
Your app handles this automatically with:
```python
with app.app_context():
    db.create_all()  # Creates tables if they don't exist
```

## Post-Deployment Steps

1. **Create Your First Admin User**
   - Register through the web interface
   - Or use Railway console to run user creation script

2. **Test Core Functionality**
   - ✅ User registration/login
   - ✅ Transaction upload
   - ✅ File management
   - ✅ Reports generation

3. **Set Up Monitoring**
   - Enable Railway's monitoring features
   - Consider external monitoring if needed

4. **Backup Strategy**
   - Railway handles database backups
   - Consider exporting user data periodically

## Security Best Practices for Production

### Already Implemented ✅
- Multi-user data isolation
- CSRF protection
- XSS prevention
- SQL injection protection
- Secure session management
- Input validation
- File upload restrictions

### Additional Recommendations
1. **Regular Updates**
   - Monitor for security updates in dependencies
   - Update Python and Flask regularly

2. **Monitoring**
   - Set up uptime monitoring
   - Configure error alerting

3. **Backup Verification**
   - Test database restore procedures
   - Verify file upload backups

## Success! 🎉

Once deployed, your iBeekeeper app will be available at:
`https://your-app-name.railway.app`

With features:
- 🐝 Modern iOS/macOS UI
- 🔐 Secure multi-user authentication
- 📊 Transaction management
- 📁 File upload/management
- 📈 Reporting capabilities
- 🌙 Dark mode support

---

## Need Help?

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **GitHub Issues**: Create issues in your repository

Your iBeekeeper application is production-ready and configured for Railway deployment! 🚀