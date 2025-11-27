# Legal Documents Generator

## Overview
A comprehensive Flask web application for managing contract templates with electronic signature capture and PDF generation. The system includes 40+ pre-populated professional contract templates across 7 categories, dynamic variable detection, e-signature functionality, and PDF export capabilities.

## Features
- **Template Management**: Create, edit, delete, and organize contract templates
- **Pre-populated Templates**: 40 professional contract templates in 7 categories:
  - Business & Employment (8 templates)
  - Real Estate (5 templates)
  - Financial & Loans (5 templates)
  - Services & Freelance (6 templates)
  - Legal & Personal (6 templates)
  - Purchase & Sales (4 templates)
  - Tech & IP (6 templates)
- **Variable Detection**: Automatically detects variables in curly braces (e.g., {client_name})
- **Dynamic Forms**: Auto-generates input forms based on detected variables
- **E-Signature**: HTML5 canvas signature capture using Signature Pad JS
- **PDF Export**: Generate professional PDFs with embedded signatures using WeasyPrint
- **Bootstrap 5 UI**: Clean, responsive, and modern interface

## Technology Stack
- **Backend**: Flask, Flask-SQLAlchemy, Flask-WTF (CSRF protection)
- **Database**: SQLite
- **PDF Generation**: WeasyPrint
- **Security**: CSRF protection, input validation, HTML escaping
- **Frontend**: Bootstrap 5, Signature Pad JS
- **Python Version**: 3.11

## Project Structure
```
.
├── app.py                  # Main Flask application with routes and models
├── templates/              # HTML templates
│   ├── base.html          # Base template with navigation
│   ├── index.html         # Home page listing all templates
│   ├── create_template.html # Create new template form
│   ├── edit_template.html  # Edit template form
│   ├── generate_contract.html # Fill variables and capture signature
│   └── preview.html       # Preview and download contract PDF
├── contracts.db           # SQLite database (auto-created)
├── pyproject.toml         # Python dependencies
└── .gitignore            # Git ignore rules

## Routes
- `/` - List all templates by category
- `/create-template` - Create new contract template
- `/edit-template/<id>` - Edit existing template
- `/delete-template/<id>` - Delete template
- `/generate-contract/<id>` - Fill variables and add signature
- `/download-pdf` - Generate and download PDF with signature

## Database Schema
**Template Model:**
- `id`: Primary key
- `title`: Template name
- `category`: Template category
- `content`: Template text with variables
- `created_at`: Timestamp

## How to Use
1. Browse templates on the home page organized by category
2. Click "Generate" on any template to create a contract
3. Fill in the required variables (auto-detected from template)
4. Draw your signature on the canvas
5. Preview the completed contract
6. Download as PDF with embedded signature

## Development Notes
- First run automatically initializes database with sample templates
- Variables in templates use {variable_name} format
- Signature captured as base64 PNG image
- PDF includes contract content and signature image
- No authentication required (all templates are global)

## Environment Variables
- `SESSION_SECRET`: Flask secret key (auto-set by Replit)

## Security Features
- **CSRF Protection**: Flask-WTF CSRF tokens on all POST forms
- **HTML Injection Prevention**: All user inputs properly escaped in PDF generation
- **Input Validation**: Length limits and format validation for template fields
- **Signature Validation**: Data URL format validation for e-signatures
- **Error Handling**: Specific exceptions with user-friendly error messages

## Recent Changes
- **October 14, 2025 (Security Audit)**: Comprehensive security improvements
  - **CSRF Protection**: Added Flask-WTF CSRF protection to all POST routes (create, edit, delete, generate, download-pdf)
  - **HTML Injection Fix**: Implemented proper HTML escaping for template title, content, and signature in PDF generation
  - **Signature Security**: Added data URL validation (must start with 'data:image/') and HTML escaping with quote protection
  - **Input Validation**: Added length limits for template title (200 chars) and category (100 chars)
  - **Error Handling**: Replaced bare exceptions with specific ValueError handlers for date/currency validation
  - **Code Cleanup**: Removed unused /static route, PWA files, and empty static folder
  - **Type Safety**: Fixed SQLAlchemy LSP typing errors

- **October 14, 2025**: Initial implementation with full feature set
  - Created Flask app with SQLAlchemy models
  - Implemented all CRUD operations for templates
  - Added 40 pre-populated professional contract templates across 7 categories
  - Integrated Signature Pad JS for e-signature capture
  - Implemented PDF generation with WeasyPrint
  - Created responsive Bootstrap 5 UI
  - Fixed delete operation to use POST method for CSRF protection
  - All security and functionality requirements verified
