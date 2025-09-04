# Bookkeeping App

A simple web-based bookkeeping application that syncs with Wise API for transaction management, document matching, and basic financial reporting.

## Features

- 🔄 **Wise API Integration**: Sync transactions from your Wise account
- 📎 **Document Management**: Upload and link PDF documents to transactions
- 🏷️ **Transaction Coding**: Categorize transactions as Revenue or Expense
- 📊 **Reporting**: Generate reports and export to Excel
- 🌐 **Web Interface**: Clean, responsive web interface
- ☁️ **Cloud Ready**: Designed for Railway deployment

## Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript with Bootstrap
- **Deployment**: Railway.app

## Local Development Setup

### Prerequisites
- Python 3.8+
- pip

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd bookkeeping
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the app**
   Open your browser to `http://localhost:5000`

## Railway Deployment

### One-Click Deploy
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template/your-template-id)

### Manual Deployment

1. **Create Railway account** at [railway.app](https://railway.app)

2. **Connect your GitHub repository**
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository

3. **Set environment variables**
   In Railway dashboard, go to your project → Variables and add:
   ```
   SECRET_KEY=your-secret-key-here
   WISE_API_TOKEN=your-wise-api-token
   WISE_API_URL=https://api.wise.com
   FLASK_DEBUG=False
   ```

4. **Deploy**
   Railway will automatically deploy your app and provide a URL.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | Random key |
| `DATABASE_URL` | Database connection string | `sqlite:///database.db` |
| `WISE_API_TOKEN` | Your Wise API token | Required |
| `WISE_API_URL` | Wise API base URL | `https://api.wise.com` |
| `UPLOAD_FOLDER` | Directory for uploaded files | `uploads` |
| `MAX_CONTENT_LENGTH` | Max file upload size (bytes) | `16777216` (16MB) |

### Wise API Setup

1. **Get API Access**:
   - Log into your Wise account
   - Go to Settings → API tokens
   - Create a new token with read permissions

2. **Update Configuration**:
   - Add your token to the `WISE_API_TOKEN` environment variable
   - Currently using dummy data - replace with real API calls in `services/wise_api.py`

## Usage

### 1. Sync Transactions
- Click "Sync Wise Transactions" to pull latest transactions from Wise
- Transactions appear in the Transactions list

### 2. Match Documents
- Click "Manage" on any transaction
- Upload PDF invoices, receipts, or bills
- Files are automatically organized and linked

### 3. Code Transactions
- Select Revenue or Expense category
- Add notes if needed
- Save coding

### 4. Generate Reports
- Go to Reports section
- Select date range
- View summary and export to Excel

## File Structure

```
bookkeeping/
├── app.py                 # Main Flask application
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── Procfile             # Railway deployment config
├── models/              # Database models
├── services/            # Business logic services
├── routes/              # URL routes and views
├── templates/           # HTML templates
├── static/              # CSS, JS, images
└── uploads/             # Uploaded PDF files
```

## Development

### Adding New Features

1. **Models**: Add database models in `models/`
2. **Services**: Add business logic in `services/`
3. **Routes**: Add URL handlers in `routes/`
4. **Templates**: Add HTML templates in `templates/`

### Database Migrations

For schema changes:
```bash
# Delete existing database
rm database.db

# Restart application (will recreate tables)
python app.py
```

## Security Notes

- Never commit real API tokens to version control
- Use environment variables for sensitive configuration
- Uploaded files are stored locally (consider cloud storage for production)
- HTTPS is automatically provided by Railway

## Troubleshooting

### Common Issues

1. **File Upload Errors**
   - Check file size (max 16MB)
   - Ensure only PDF files are uploaded

2. **Wise API Errors**
   - Verify API token is correct
   - Check API rate limits

3. **Database Issues**
   - Delete `database.db` to reset
   - Check file permissions

### Logs

- Railway: View logs in Railway dashboard
- Local: Check terminal output

## License

MIT License - see LICENSE file for details

## Support

For issues and feature requests, please create an issue in the GitHub repository.