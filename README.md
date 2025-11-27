# Legal Documents Generator

A comprehensive Flask web application for managing contract templates with electronic signature capture and PDF generation.

## Features

✨ **40 Pre-loaded Templates** across 7 categories:
- Business & Employment (8 templates)
- Real Estate (5 templates)  
- Financial & Loans (5 templates)
- Services & Freelance (6 templates)
- Legal & Personal (6 templates)
- Purchase & Sales (4 templates)
- Tech & IP (6 templates)

🔧 **Smart Variable Detection** - Automatically finds and fills variables like `{client_name}`, `{date}`, etc.

✍️ **E-Signature Capture** - HTML5 canvas signature with Signature Pad JS

📄 **PDF Export** - Professional PDFs with embedded signatures using WeasyPrint

🎨 **Modern UI** - Clean, responsive Bootstrap 5 interface

## How to Use

### 1. Browse Templates
- Visit the home page to see all available templates organized by category
- Click on any category to view templates in that group

### 2. Generate a Contract
1. Click the **Generate** button on any template
2. Fill in the required information (automatically detected from template variables)
3. Draw your signature on the canvas
4. Click **Generate Contract** to preview

### 3. Download PDF
- Review the filled contract with your signature
- Click **Download PDF** to save the contract

### 4. Manage Templates
- **Create New**: Click "New Template" to add custom templates
- **Edit**: Modify existing templates with the Edit button
- **Delete**: Remove unwanted templates (requires confirmation)

## Template Variables

Use curly braces `{}` to create fillable variables in your templates:

```
This agreement is made on {date} between {party1_name} and {party2_name}.
The total amount is {amount} payable by {payment_date}.
```

The system will automatically:
- Detect all variables
- Generate input forms
- Fill in values when generating contracts

## Installation (Replit)

Dependencies are already installed:
- Flask
- Flask-SQLAlchemy
- WeasyPrint

The app runs automatically when you start the Replit workspace.

## Local Installation

```bash
# Install dependencies
pip install flask flask-sqlalchemy weasyprint

# Run the application
python app.py
```

Visit `http://localhost:5000` in your browser.

## Technology Stack

- **Backend**: Flask, SQLAlchemy
- **Database**: SQLite
- **PDF Generation**: WeasyPrint
- **Frontend**: Bootstrap 5, Signature Pad JS
- **Python**: 3.11

## Project Structure

```
.
├── app.py                      # Main Flask application
├── templates/                  # HTML templates
│   ├── base.html              # Base layout
│   ├── index.html             # Home page
│   ├── create_template.html   # Create template form
│   ├── edit_template.html     # Edit template form
│   ├── generate_contract.html # Contract generation
│   └── preview.html           # Preview & download
├── contracts.db               # SQLite database
├── README.md                  # This file
└── replit.md                  # Project documentation
```

## Security

- ✅ CSRF protection via POST methods for destructive actions
- ✅ SQLAlchemy ORM prevents SQL injection
- ✅ Secure session management with secret keys
- ✅ Input validation on all forms

## Support

For questions or issues, please refer to the project documentation in `replit.md`.

---

Built with ❤️ using Flask and Bootstrap 5
