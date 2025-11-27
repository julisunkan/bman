import os
import re
import base64
import uuid
from flask import Flask, render_template, request, redirect, url_for, make_response, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contracts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CONTRACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_contracts')
if not os.path.exists(CONTRACTS_DIR):
    os.makedirs(CONTRACTS_DIR)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

class Template(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contracts = db.relationship('Contract', backref='template', lazy=True)
    
    def __repr__(self):
        return f'<Template {self.title}>'

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    template_id = db.Column(db.Integer, db.ForeignKey('template.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    filled_content = db.Column(db.Text, nullable=False)
    signature_data = db.Column(db.Text)
    pdf_filename = db.Column(db.String(255), nullable=False)
    variables_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Contract {self.title}>'

def extract_variables(content):
    """Extract variables from template content (e.g., {client_name})"""
    pattern = r'\{([^}]+)\}'
    variables = re.findall(pattern, content)
    return list(set(variables))

def fill_template(content, variables_dict):
    """Fill template content with provided variable values"""
    filled_content = content
    for var, value in variables_dict.items():
        filled_content = filled_content.replace(f'{{{var}}}', value)
    return filled_content

@app.route('/')
def index():
    templates = Template.query.order_by(Template.category, Template.title).all()
    
    templates_by_category = {}
    for template in templates:
        if template.category not in templates_by_category:
            templates_by_category[template.category] = []
        templates_by_category[template.category].append(template)
    
    success_message = request.args.get('success_message')
    
    return render_template('index.html', templates_by_category=templates_by_category, success_message=success_message)

@app.route('/create-template', methods=['GET', 'POST'])
def create_template():
    message = None
    message_type = None
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not category or not content:
            message = 'All fields are required!'
            message_type = 'danger'
            return render_template('create_template.html', message=message, message_type=message_type)
        
        if len(title) > 200:
            message = 'Template title must be 200 characters or less!'
            message_type = 'danger'
            return render_template('create_template.html', message=message, message_type=message_type)
        
        if len(category) > 100:
            message = 'Category name must be 100 characters or less!'
            message_type = 'danger'
            return render_template('create_template.html', message=message, message_type=message_type)
        
        new_template = Template(title=title, category=category, content=content)  # type: ignore
        db.session.add(new_template)
        db.session.commit()
        
        return redirect(url_for('index', success_message=f'Template "{title}" created successfully!'))
    
    return render_template('create_template.html', message=message, message_type=message_type)

@app.route('/edit-template/<int:id>', methods=['GET', 'POST'])
def edit_template(id):
    template = Template.query.get_or_404(id)
    message = None
    message_type = None
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not category or not content:
            message = 'All fields are required!'
            message_type = 'danger'
            return render_template('edit_template.html', template=template, message=message, message_type=message_type)
        
        if len(title) > 200:
            message = 'Template title must be 200 characters or less!'
            message_type = 'danger'
            return render_template('edit_template.html', template=template, message=message, message_type=message_type)
        
        if len(category) > 100:
            message = 'Category name must be 100 characters or less!'
            message_type = 'danger'
            return render_template('edit_template.html', template=template, message=message, message_type=message_type)
        
        template.title = title
        template.category = category
        template.content = content
        
        db.session.commit()
        return redirect(url_for('index', success_message=f'Template "{template.title}" updated successfully!'))
    
    return render_template('edit_template.html', template=template, message=message, message_type=message_type)

@app.route('/delete-template/<int:id>', methods=['POST'])
def delete_template(id):
    template = Template.query.get_or_404(id)
    title = template.title
    
    db.session.delete(template)
    db.session.commit()
    
    return redirect(url_for('index', success_message=f'Template "{title}" deleted successfully!'))

@app.route('/generate-contract/<int:id>', methods=['GET', 'POST'])
def generate_contract(id):
    template = Template.query.get_or_404(id)
    variables = extract_variables(template.content)
    
    if request.method == 'POST':
        variables_dict = {}
        error_message = None
        
        for var in variables:
            value = request.form.get(var, '')
            # Format date fields nicely
            if 'date' in var.lower() and value:
                try:
                    date_obj = datetime.strptime(value, '%Y-%m-%d')
                    value = date_obj.strftime('%B %d, %Y')
                except ValueError:
                    error_message = f'Invalid date format for {var.replace("_", " ").title()}. Please use a valid date.'
                    break
            # Handle currency fields
            elif any(keyword in var.lower() for keyword in ['amount', 'price', 'fee', 'cost', 'salary', 'rent', 'payment']) and value:
                currency = request.form.get(f'{var}_currency', '$')
                try:
                    float(value)
                    value = f'{currency}{value}'
                except ValueError:
                    error_message = f'Invalid number format for {var.replace("_", " ").title()}. Please enter a valid number.'
                    break
            variables_dict[var] = value
        
        if error_message:
            return render_template('generate_contract.html', template=template, variables=variables, 
                                 error_message=error_message)
        
        signature_data = request.form.get('signature')
        
        filled_content = fill_template(template.content, variables_dict)
        
        return render_template('preview.html', 
                             template=template, 
                             content=filled_content, 
                             signature=signature_data,
                             variables=variables_dict,
                             now=datetime.now())
    
    return render_template('generate_contract.html', template=template, variables=variables)

@app.route('/admin')
def admin():
    templates = Template.query.order_by(Template.category, Template.title).all()
    
    templates_by_category = {}
    for template in templates:
        if template.category not in templates_by_category:
            templates_by_category[template.category] = []
        templates_by_category[template.category].append(template)
    
    return render_template('admin.html', templates_by_category=templates_by_category)

def generate_pdf_html(title, content, signature):
    """Generate HTML for PDF conversion"""
    import html as html_module
    
    escaped_title = html_module.escape(title)
    escaped_content = html_module.escape(content)
    
    if signature and not signature.startswith('data:image/'):
        signature = ''
    
    escaped_signature = html_module.escape(signature, quote=True) if signature else ''
    
    signature_section = ''
    if escaped_signature:
        signature_section = f'''
        <div class="signature-section">
            <p><strong>Electronic Signature:</strong></p>
            <img src="{escaped_signature}" class="signature-image" alt="Signature" />
            <p style="margin-top: 20px;"><small>Signed on: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</small></p>
        </div>
        '''
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @font-face {{
                font-family: 'DejaVu Sans';
                src: local('DejaVu Sans');
            }}
            body {{
                font-family: 'DejaVu Sans', Arial, sans-serif;
                line-height: 1.6;
                margin: 40px;
                color: #333;
            }}
            .contract-content {{
                white-space: pre-wrap;
                margin-bottom: 40px;
            }}
            .signature-section {{
                margin-top: 60px;
                border-top: 2px solid #333;
                padding-top: 20px;
            }}
            .signature-image {{
                max-width: 300px;
                border: 1px solid #ccc;
                padding: 10px;
                margin-top: 10px;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>{escaped_title}</h1>
        <div class="contract-content">{escaped_content}</div>
        {signature_section}
    </body>
    </html>
    '''

def save_contract_pdf(template_id, title, content, signature, variables_dict):
    """Save a contract to the database and generate PDF file"""
    from weasyprint import HTML
    import json
    
    contract_uuid = str(uuid.uuid4())
    safe_filename = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).replace(' ', '_')
    pdf_filename = f"{safe_filename}_{contract_uuid[:8]}.pdf"
    pdf_path = os.path.join(CONTRACTS_DIR, pdf_filename)
    
    html_content = generate_pdf_html(title, content, signature)
    HTML(string=html_content, encoding='utf-8').write_pdf(pdf_path)
    
    contract = Contract(
        uuid=contract_uuid,
        template_id=template_id,
        title=title,
        filled_content=content,
        signature_data=signature,
        pdf_filename=pdf_filename,
        variables_json=json.dumps(variables_dict) if variables_dict else None
    )
    db.session.add(contract)
    db.session.commit()
    
    return contract

@app.route('/save-and-download/<int:template_id>', methods=['POST'])
def save_and_download(template_id):
    """Save contract to database and redirect to download"""
    content = request.form.get('content', '')
    signature = request.form.get('signature', '')
    template_title = request.form.get('template_title', 'contract')
    variables_json = request.form.get('variables_json', '{}')
    
    import json
    try:
        variables_dict = json.loads(variables_json)
    except json.JSONDecodeError:
        variables_dict = {}
    
    contract = save_contract_pdf(template_id, template_title, content, signature, variables_dict)
    
    return redirect(url_for('download_contract', contract_uuid=contract.uuid))

@app.route('/download/<contract_uuid>')
def download_contract(contract_uuid):
    """Server-side download of stored contract PDF"""
    contract = Contract.query.filter_by(uuid=contract_uuid).first_or_404()
    pdf_path = os.path.join(CONTRACTS_DIR, contract.pdf_filename)
    
    if not os.path.exists(pdf_path):
        abort(404, description="PDF file not found")
    
    return send_file(
        pdf_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=contract.pdf_filename
    )

@app.route('/contracts')
def contracts_list():
    """View all generated contracts"""
    contracts = Contract.query.order_by(Contract.created_at.desc()).all()
    return render_template('contracts.html', contracts=contracts)

@app.route('/contract/<contract_uuid>')
def view_contract(contract_uuid):
    """View a specific contract"""
    contract = Contract.query.filter_by(uuid=contract_uuid).first_or_404()
    return render_template('view_contract.html', contract=contract)

@app.route('/delete-contract/<contract_uuid>', methods=['POST'])
def delete_contract(contract_uuid):
    """Delete a contract and its PDF file"""
    contract = Contract.query.filter_by(uuid=contract_uuid).first_or_404()
    
    pdf_path = os.path.join(CONTRACTS_DIR, contract.pdf_filename)
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    
    db.session.delete(contract)
    db.session.commit()
    
    return redirect(url_for('contracts_list', success_message='Contract deleted successfully!'))

def init_db():
    """Initialize database with sample templates"""
    with app.app_context():
        db.create_all()
        
        if Template.query.count() == 0:
            templates_data = [
                # Business & Employment
                {
                    'title': 'Non-Disclosure Agreement (NDA)',
                    'category': 'Business & Employment',
                    'content': '''NON-DISCLOSURE AGREEMENT

This Non-Disclosure Agreement ("Agreement") is entered into on {date} by and between:

Disclosing Party: {disclosing_party_name}
Receiving Party: {receiving_party_name}

1. CONFIDENTIAL INFORMATION
The Receiving Party acknowledges that it may receive confidential information from the Disclosing Party regarding {business_purpose}.

2. OBLIGATIONS
The Receiving Party agrees to:
- Maintain confidentiality of all disclosed information
- Use the information solely for {intended_purpose}
- Not disclose information to third parties without written consent

3. TERM
This Agreement shall remain in effect for {term_duration} from the date of signing.

4. GOVERNING LAW
This Agreement shall be governed by the laws of {jurisdiction}.

By signing below, both parties agree to the terms outlined in this Agreement.'''
                },
                {
                    'title': 'Employment Agreement',
                    'category': 'Business & Employment',
                    'content': '''EMPLOYMENT AGREEMENT

This Employment Agreement is made on {date} between:

Employer: {employer_name}
Employee: {employee_name}

1. POSITION
The Employee is hired for the position of {job_title}.

2. COMPENSATION
The Employee will receive a salary of {salary} per {pay_period}.

3. START DATE
Employment will commence on {start_date}.

4. DUTIES AND RESPONSIBILITIES
The Employee agrees to perform duties including: {job_duties}

5. WORK HOURS
Standard work hours are {work_hours} per week.

6. BENEFITS
The Employee is entitled to: {benefits}

7. TERMINATION
Either party may terminate this agreement with {notice_period} notice.

Employee Signature: _______________  Date: _______________
Employer Signature: _______________  Date: _______________'''
                },
                {
                    'title': 'Independent Contractor Agreement',
                    'category': 'Business & Employment',
                    'content': '''INDEPENDENT CONTRACTOR AGREEMENT

This Agreement is made on {date} between:

Client: {client_name}
Contractor: {contractor_name}

1. SERVICES
The Contractor agrees to provide the following services: {services_description}

2. PAYMENT
The Client agrees to pay {payment_amount} for the services, payable {payment_terms}.

3. TERM
This contract is effective from {start_date} to {end_date}.

4. INDEPENDENT CONTRACTOR STATUS
The Contractor is an independent contractor, not an employee, and is responsible for all taxes.

5. DELIVERABLES
The Contractor will deliver: {deliverables}

Agreed and Accepted:
Contractor: _______________  Date: _______________
Client: _______________  Date: _______________'''
                },
                {
                    'title': 'Partnership Agreement',
                    'category': 'Business & Employment',
                    'content': '''PARTNERSHIP AGREEMENT

This Partnership Agreement is entered into on {date} by and between:

Partner 1: {partner1_name}
Partner 2: {partner2_name}

1. BUSINESS PURPOSE
The partners agree to conduct business as {business_name} for the purpose of {business_purpose}.

2. CAPITAL CONTRIBUTIONS
Partner 1 contributes: {partner1_contribution}
Partner 2 contributes: {partner2_contribution}

3. PROFIT AND LOSS SHARING
Profits and losses shall be shared: {profit_sharing_ratio}

4. MANAGEMENT
Both partners shall have equal management rights unless otherwise agreed.

5. TERM
This partnership shall continue until {end_date} or until terminated by mutual agreement.

Partner 1 Signature: _______________  Date: _______________
Partner 2 Signature: _______________  Date: _______________'''
                },
                {
                    'title': 'Non-Compete Agreement',
                    'category': 'Business & Employment',
                    'content': '''NON-COMPETE AGREEMENT

This Non-Compete Agreement is made on {date} between:

Company: {company_name}
Employee: {employee_name}

1. NON-COMPETE COVENANT
The Employee agrees not to engage in any business that competes with {company_name} within {geographic_area} for a period of {duration} following termination of employment.

2. RESTRICTED ACTIVITIES
The Employee shall not:
- Work for competitors
- Solicit company clients
- Disclose trade secrets or confidential information

3. CONSIDERATION
In exchange for this agreement, the Employee receives {consideration}.

4. SEVERABILITY
If any provision is found unenforceable, the remaining provisions shall remain in effect.

Employee Signature: _______________  Date: _______________
Company Representative: _______________  Date: _______________'''
                },
                {
                    'title': 'Consulting Agreement',
                    'category': 'Business & Employment',
                    'content': '''CONSULTING AGREEMENT

This Agreement is made on {date} between:

Client: {client_name}
Consultant: {consultant_name}

1. CONSULTING SERVICES
The Consultant agrees to provide consulting services for {project_description}.

2. COMPENSATION
The Client will pay {rate} per {time_unit} for a total not to exceed {maximum_amount}.

3. TERM
Services will be provided from {start_date} to {end_date}.

4. DELIVERABLES
The Consultant will deliver: {deliverables}

5. EXPENSES
{expense_policy}

Consultant: _______________  Date: _______________
Client: _______________  Date: _______________'''
                },
                {
                    'title': 'Offer Letter',
                    'category': 'Business & Employment',
                    'content': '''OFFER LETTER

Date: {date}

Dear {candidate_name},

We are pleased to offer you the position of {job_title} at {company_name}.

POSITION DETAILS:
- Start Date: {start_date}
- Salary: {salary} per year
- Benefits: {benefits}
- Reporting to: {supervisor_name}

This offer is contingent upon {contingencies}.

Please sign and return this letter by {response_deadline} to accept this offer.

We look forward to welcoming you to our team!

Sincerely,
{hiring_manager_name}
{company_name}

Acceptance:
I accept this offer of employment.

Signature: _______________  Date: _______________'''
                },
                
                # Real Estate
                {
                    'title': 'Residential Lease Agreement',
                    'category': 'Real Estate',
                    'content': '''RESIDENTIAL LEASE AGREEMENT

This Lease Agreement is made on {date} between:

Landlord: {landlord_name}
Tenant: {tenant_name}

1. PROPERTY
The Landlord agrees to lease the property located at {property_address}.

2. TERM
The lease term is from {start_date} to {end_date}.

3. RENT
Monthly rent is {rent_amount}, due on the {due_day} of each month.

4. SECURITY DEPOSIT
A security deposit of {deposit_amount} is required.

5. UTILITIES
{utilities_responsibility}

6. MAINTENANCE
Tenant is responsible for: {tenant_responsibilities}
Landlord is responsible for: {landlord_responsibilities}

Landlord Signature: _______________  Date: _______________
Tenant Signature: _______________  Date: _______________'''
                },
                {
                    'title': 'Commercial Lease Agreement',
                    'category': 'Real Estate',
                    'content': '''COMMERCIAL LEASE AGREEMENT

This Commercial Lease is made on {date} between:

Landlord: {landlord_name}
Tenant/Business: {tenant_business_name}

1. PREMISES
The Landlord leases to Tenant the commercial space located at {property_address}, consisting of approximately {square_footage} square feet.

2. TERM
Lease term: {lease_term} beginning {start_date}.

3. RENT
Base rent: {monthly_rent} per month, plus {additional_charges}.

4. USE
The premises shall be used for {business_purpose}.

5. MAINTENANCE AND REPAIRS
{maintenance_terms}

Landlord: _______________  Date: _______________
Tenant: _______________  Date: _______________'''
                },
                {
                    'title': 'Rental Application',
                    'category': 'Real Estate',
                    'content': '''RENTAL APPLICATION

Property Address: {property_address}
Application Date: {date}

APPLICANT INFORMATION:
Name: {applicant_name}
Current Address: {current_address}
Phone: {phone_number}
Email: {email_address}

EMPLOYMENT:
Employer: {employer_name}
Position: {job_title}
Monthly Income: {monthly_income}

RENTAL HISTORY:
Previous Landlord: {previous_landlord}
Previous Address: {previous_address}
Rent Amount: {previous_rent}

REFERENCES:
{references}

I authorize a credit and background check.

Applicant Signature: _______________  Date: _______________'''
                },
                {
                    'title': 'Roommate Agreement',
                    'category': 'Real Estate',
                    'content': '''ROOMMATE AGREEMENT

This Agreement is made on {date} between roommates sharing the property at {property_address}:

Roommate 1: {roommate1_name}
Roommate 2: {roommate2_name}

1. RENT DIVISION
Total rent: {total_rent}
Roommate 1 pays: {roommate1_share}
Roommate 2 pays: {roommate2_share}

2. UTILITIES
Utilities will be split: {utility_split}

3. SHARED SPACES
{shared_space_rules}

4. QUIET HOURS
{quiet_hours}

5. GUESTS
{guest_policy}

6. CLEANING
{cleaning_responsibilities}

Roommate 1: _______________  Date: _______________
Roommate 2: _______________  Date: _______________'''
                },
                {
                    'title': 'Property Sale Agreement',
                    'category': 'Real Estate',
                    'content': '''PROPERTY SALE AGREEMENT

This Agreement is made on {date} between:

Seller: {seller_name}
Buyer: {buyer_name}

1. PROPERTY
The Seller agrees to sell the property located at {property_address}.

2. PURCHASE PRICE
The purchase price is {purchase_price}, to be paid as follows: {payment_terms}

3. CLOSING DATE
The sale will close on {closing_date}.

4. CONDITION
The property is sold {condition_terms}.

5. CONTINGENCIES
This sale is contingent upon: {contingencies}

Seller Signature: _______________  Date: _______________
Buyer Signature: _______________  Date: _______________'''
                },
                
                # Financial & Loans
                {
                    'title': 'Promissory Note',
                    'category': 'Financial & Loans',
                    'content': '''PROMISSORY NOTE

Principal Amount: {loan_amount}
Date: {date}

FOR VALUE RECEIVED, {borrower_name} ("Borrower") promises to pay {lender_name} ("Lender") the principal sum of {loan_amount}.

INTEREST RATE: {interest_rate}% per annum

PAYMENT TERMS:
{payment_schedule}

DUE DATE: {due_date}

DEFAULT:
If Borrower fails to make any payment when due, the entire unpaid balance shall become immediately due and payable.

Borrower Signature: _______________  Date: _______________'''
                },
                {
                    'title': 'Loan Agreement',
                    'category': 'Financial & Loans',
                    'content': '''LOAN AGREEMENT

This Loan Agreement is made on {date} between:

Lender: {lender_name}
Borrower: {borrower_name}

1. LOAN AMOUNT
The Lender agrees to loan {loan_amount} to the Borrower.

2. INTEREST
Interest rate: {interest_rate}% per {interest_period}

3. REPAYMENT
The Borrower will repay the loan in {number_of_payments} payments of {payment_amount} each, beginning on {first_payment_date}.

4. LATE FEES
Late payments will incur a fee of {late_fee}.

5. COLLATERAL
{collateral_description}

Lender: _______________  Date: _______________
Borrower: _______________  Date: _______________'''
                },
                {
                    'title': 'Installment Payment Agreement',
                    'category': 'Financial & Loans',
                    'content': '''INSTALLMENT PAYMENT AGREEMENT

Date: {date}

Creditor: {creditor_name}
Debtor: {debtor_name}

TOTAL AMOUNT OWED: {total_amount}

PAYMENT PLAN:
The Debtor agrees to pay the amount in {number_of_installments} installments of {installment_amount} each.

PAYMENT SCHEDULE:
First payment due: {first_payment_date}
Subsequent payments due: {payment_frequency}

If any payment is more than {grace_period} days late, the entire balance becomes due immediately.

Creditor: _______________  Date: _______________
Debtor: _______________  Date: _______________'''
                },
                {
                    'title': 'Debt Acknowledgement Form',
                    'category': 'Financial & Loans',
                    'content': '''DEBT ACKNOWLEDGEMENT

Date: {date}

I, {debtor_name}, acknowledge that I owe {creditor_name} the sum of {debt_amount}.

REASON FOR DEBT:
{debt_reason}

PAYMENT AGREEMENT:
{payment_terms}

I agree to repay this debt according to the terms outlined above.

Debtor Signature: _______________  Date: _______________
Creditor Signature: _______________  Date: _______________'''
                },
                
                # Services & Freelance
                {
                    'title': 'Freelance Contract',
                    'category': 'Services & Freelance',
                    'content': '''FREELANCE CONTRACT

This Contract is made on {date} between:

Client: {client_name}
Freelancer: {freelancer_name}

1. PROJECT DESCRIPTION
{project_description}

2. DELIVERABLES
{deliverables}

3. TIMELINE
Project start: {start_date}
Deadline: {deadline}

4. PAYMENT
Total fee: {total_fee}
Payment schedule: {payment_schedule}

5. REVISIONS
{revision_policy}

6. OWNERSHIP
{ownership_terms}

Client: _______________  Date: _______________
Freelancer: _______________  Date: _______________'''
                },
                {
                    'title': 'Service Agreement',
                    'category': 'Services & Freelance',
                    'content': '''SERVICE AGREEMENT

This Agreement is made on {date} between:

Service Provider: {provider_name}
Client: {client_name}

1. SERVICES
The Provider agrees to provide: {services_description}

2. TERM
Services will be provided from {start_date} to {end_date}.

3. FEES
{fee_structure}

4. PAYMENT TERMS
{payment_terms}

5. TERMINATION
{termination_terms}

Provider: _______________  Date: _______________
Client: _______________  Date: _______________'''
                },
                {
                    'title': 'Maintenance Contract',
                    'category': 'Services & Freelance',
                    'content': '''MAINTENANCE CONTRACT

Date: {date}

Service Provider: {provider_name}
Client: {client_name}

1. MAINTENANCE SERVICES
The Provider will perform the following maintenance: {maintenance_description}

2. SCHEDULE
Maintenance will be performed {maintenance_frequency}.

3. RESPONSE TIME
Emergency response within: {emergency_response_time}
Standard service within: {standard_response_time}

4. FEES
Monthly fee: {monthly_fee}
Emergency service rate: {emergency_rate}

5. TERM
Contract period: {contract_duration}

Provider: _______________  Date: _______________
Client: _______________  Date: _______________'''
                },
                {
                    'title': 'Event Planning Contract',
                    'category': 'Services & Freelance',
                    'content': '''EVENT PLANNING CONTRACT

Date: {date}

Event Planner: {planner_name}
Client: {client_name}

EVENT DETAILS:
Event: {event_name}
Date: {event_date}
Location: {event_location}
Expected Attendance: {expected_attendance}

SERVICES:
{services_included}

FEES:
Total fee: {total_fee}
Deposit: {deposit_amount} due {deposit_date}
Balance due: {balance_date}

CANCELLATION:
{cancellation_policy}

Planner: _______________  Date: _______________
Client: _______________  Date: _______________'''
                },
                
                # Legal & Personal
                {
                    'title': 'Power of Attorney',
                    'category': 'Legal & Personal',
                    'content': '''POWER OF ATTORNEY

I, {principal_name}, residing at {principal_address}, hereby appoint {agent_name} as my attorney-in-fact (Agent).

EFFECTIVE DATE: {effective_date}

POWERS GRANTED:
My Agent is authorized to: {powers_description}

LIMITATIONS:
{limitations}

DURATION:
This Power of Attorney shall {duration_terms}.

REVOCATION:
I reserve the right to revoke this Power of Attorney at any time.

Principal Signature: _______________  Date: _______________

Witness 1: _______________  Date: _______________
Witness 2: _______________  Date: _______________'''
                },
                {
                    'title': 'Living Will',
                    'category': 'Legal & Personal',
                    'content': '''LIVING WILL

I, {declarant_name}, being of sound mind, make this Living Will to express my wishes regarding medical treatment.

HEALTHCARE DECISIONS:
If I am unable to make my own medical decisions, I direct that: {medical_wishes}

LIFE-SUSTAINING TREATMENT:
{life_support_wishes}

HEALTHCARE AGENT:
I appoint {agent_name} as my healthcare agent to make decisions on my behalf.

ORGAN DONATION:
{organ_donation_wishes}

Declarant Signature: _______________  Date: _______________

Witness 1: _______________  Date: _______________
Witness 2: _______________  Date: _______________'''
                },
                {
                    'title': 'General Release of Liability',
                    'category': 'Legal & Personal',
                    'content': '''GENERAL RELEASE OF LIABILITY

Date: {date}

I, {releasor_name}, hereby release and discharge {releasee_name} from any and all claims, damages, or liabilities arising from {incident_description}.

This release includes, but is not limited to: {claims_covered}

I understand that this is a full and final release of all claims.

CONSIDERATION:
In exchange for this release, I have received: {consideration}

Releasor Signature: _______________  Date: _______________'''
                },
                {
                    'title': 'Cease and Desist Letter',
                    'category': 'Legal & Personal',
                    'content': '''CEASE AND DESIST LETTER

Date: {date}

To: {recipient_name}
Address: {recipient_address}

Re: Cease and Desist - {violation_description}

Dear {recipient_name},

This letter is to demand that you immediately cease and desist from {prohibited_activity}.

Your actions constitute: {legal_violation}

DEMAND:
You must immediately: {demands}

If you fail to comply within {deadline_days} days, we will pursue legal action including: {legal_remedies}

Sincerely,
{sender_name}
{sender_address}'''
                },
                {
                    'title': 'Affidavit',
                    'category': 'Legal & Personal',
                    'content': '''AFFIDAVIT

STATE OF {state}
COUNTY OF {county}

I, {affiant_name}, being duly sworn, depose and state:

1. I am over the age of 18 and competent to make this affidavit.

2. I have personal knowledge of the facts stated herein.

3. FACTS:
{statement_of_facts}

4. I declare under penalty of perjury that the foregoing is true and correct.

Affiant Signature: _______________  Date: _______________

Subscribed and sworn to before me on {date}

Notary Public: _______________
My commission expires: _______________'''
                },
                
                # Purchase & Sales
                {
                    'title': 'Bill of Sale (General)',
                    'category': 'Purchase & Sales',
                    'content': '''BILL OF SALE

Date: {date}

Seller: {seller_name}
Buyer: {buyer_name}

ITEM(S) SOLD:
{item_description}

PURCHASE PRICE: {purchase_price}

PAYMENT METHOD: {payment_method}

CONDITION: The item is sold {condition}

WARRANTY: {warranty_terms}

The Seller hereby transfers all ownership rights to the Buyer.

Seller Signature: _______________  Date: _______________
Buyer Signature: _______________  Date: _______________'''
                },
                {
                    'title': 'Vehicle Bill of Sale',
                    'category': 'Purchase & Sales',
                    'content': '''VEHICLE BILL OF SALE

Date: {date}

Seller: {seller_name}
Buyer: {buyer_name}

VEHICLE INFORMATION:
Year: {vehicle_year}
Make: {vehicle_make}
Model: {vehicle_model}
VIN: {vin_number}
Mileage: {current_mileage}

PURCHASE PRICE: {purchase_price}

PAYMENT: Paid in full by {payment_method}

The vehicle is sold "AS IS" with no warranties unless stated: {warranty_terms}

Seller Signature: _______________  Date: _______________
Buyer Signature: _______________  Date: _______________'''
                },
                {
                    'title': 'Purchase Agreement',
                    'category': 'Purchase & Sales',
                    'content': '''PURCHASE AGREEMENT

Date: {date}

Seller: {seller_name}
Buyer: {buyer_name}

1. ITEM/PROPERTY
{item_description}

2. PURCHASE PRICE
Total price: {purchase_price}

3. PAYMENT TERMS
{payment_terms}

4. DELIVERY
{delivery_terms}

5. INSPECTION PERIOD
Buyer has {inspection_days} days to inspect the item.

6. WARRANTIES
{warranty_terms}

Seller: _______________  Date: _______________
Buyer: _______________  Date: _______________'''
                },
                {
                    'title': 'Sales Commission Agreement',
                    'category': 'Purchase & Sales',
                    'content': '''SALES COMMISSION AGREEMENT

Date: {date}

Company: {company_name}
Sales Representative: {rep_name}

1. APPOINTMENT
The Company appoints the Representative to sell: {products_services}

2. TERRITORY
Sales territory: {territory}

3. COMMISSION RATE
{commission_structure}

4. PAYMENT
Commissions will be paid {payment_frequency}.

5. TERM
This agreement is effective from {start_date} to {end_date}.

Company: _______________  Date: _______________
Representative: _______________  Date: _______________'''
                },
                
                # Tech & IP
                {
                    'title': 'Software License Agreement',
                    'category': 'Tech & IP',
                    'content': '''SOFTWARE LICENSE AGREEMENT

Date: {date}

Licensor: {licensor_name}
Licensee: {licensee_name}

1. GRANT OF LICENSE
The Licensor grants the Licensee a {license_type} license to use {software_name}.

2. LICENSE FEE
{license_fee_terms}

3. PERMITTED USE
{permitted_use}

4. RESTRICTIONS
The Licensee may not: {restrictions}

5. SUPPORT AND UPDATES
{support_terms}

6. TERM
License term: {license_duration}

Licensor: _______________  Date: _______________
Licensee: _______________  Date: _______________'''
                },
                {
                    'title': 'Website Development Agreement',
                    'category': 'Tech & IP',
                    'content': '''WEBSITE DEVELOPMENT AGREEMENT

Date: {date}

Developer: {developer_name}
Client: {client_name}

1. PROJECT SCOPE
The Developer will create a website with the following specifications: {project_specifications}

2. DELIVERABLES
{deliverables}

3. TIMELINE
Project start: {start_date}
Completion date: {completion_date}

4. PAYMENT
Total fee: {total_fee}
Payment schedule: {payment_schedule}

5. REVISIONS
{revision_policy}

6. INTELLECTUAL PROPERTY
{ip_ownership_terms}

7. HOSTING AND MAINTENANCE
{hosting_maintenance_terms}

Developer: _______________  Date: _______________
Client: _______________  Date: _______________'''
                },
                {
                    'title': 'App Development Agreement',
                    'category': 'Tech & IP',
                    'content': '''APP DEVELOPMENT AGREEMENT

Date: {date}

Developer: {developer_name}
Client: {client_name}

1. APPLICATION DETAILS
Platform: {platform}
App name: {app_name}
Description: {app_description}

2. DEVELOPMENT SCOPE
{development_scope}

3. MILESTONES
{milestones}

4. COMPENSATION
Total development fee: {total_fee}
Milestone payments: {milestone_payments}

5. OWNERSHIP
{ownership_terms}

6. APP STORE SUBMISSION
{submission_terms}

Developer: _______________  Date: _______________
Client: _______________  Date: _______________'''
                },
                {
                    'title': 'Intellectual Property Assignment',
                    'category': 'Tech & IP',
                    'content': '''INTELLECTUAL PROPERTY ASSIGNMENT

Date: {date}

Assignor: {assignor_name}
Assignee: {assignee_name}

1. PROPERTY DESCRIPTION
The Assignor hereby assigns all rights, title, and interest in: {ip_description}

2. CONSIDERATION
In exchange for this assignment, the Assignor receives: {consideration}

3. REPRESENTATIONS
The Assignor represents that:
- They are the sole owner of the intellectual property
- The IP does not infringe on third-party rights
- {additional_representations}

4. FURTHER ASSURANCES
The Assignor agrees to execute any additional documents necessary to perfect this assignment.

Assignor: _______________  Date: _______________
Assignee: _______________  Date: _______________'''
                },
                {
                    'title': 'Data Processing Agreement (DPA)',
                    'category': 'Tech & IP',
                    'content': '''DATA PROCESSING AGREEMENT

Date: {date}

Data Controller: {controller_name}
Data Processor: {processor_name}

1. DEFINITIONS
Personal Data: {data_definition}
Processing: {processing_definition}

2. PROCESSING OBLIGATIONS
The Processor shall:
- Process data only on documented instructions
- Ensure confidentiality of data
- Implement appropriate security measures

3. DATA SECURITY
{security_measures}

4. SUB-PROCESSORS
{subprocessor_terms}

5. DATA SUBJECT RIGHTS
{data_subject_rights}

6. BREACH NOTIFICATION
The Processor will notify the Controller of any breach within {notification_timeframe}.

7. TERM
This DPA is effective from {start_date} and continues until {end_date}.

Controller: _______________  Date: _______________
Processor: _______________  Date: _______________'''
                },
                {
                    'title': 'Trademark License Agreement',
                    'category': 'Tech & IP',
                    'content': '''TRADEMARK LICENSE AGREEMENT

Date: {date}

Licensor: {licensor_name}
Licensee: {licensee_name}

1. GRANT OF LICENSE
The Licensor grants the Licensee a {license_type} license to use the trademark "{trademark_name}".

2. TERRITORY
Licensed territory: {territory}

3. LICENSE FEE
{license_fee_terms}

4. QUALITY CONTROL
The Licensee agrees to maintain quality standards set by the Licensor.

5. TERM
License period: {license_duration}

Licensor: _______________  Date: _______________
Licensee: _______________  Date: _______________'''
                },
                {
                    'title': 'Equipment Rental Agreement',
                    'category': 'Services & Freelance',
                    'content': '''EQUIPMENT RENTAL AGREEMENT

Date: {date}

Owner: {owner_name}
Renter: {renter_name}

EQUIPMENT DESCRIPTION:
{equipment_description}

RENTAL PERIOD:
From: {start_date}
To: {end_date}

RENTAL FEES:
{rental_fee_terms}

DEPOSIT:
Security deposit: {deposit_amount}

RESPONSIBILITIES:
The Renter is responsible for: {renter_responsibilities}

Owner: _______________  Date: _______________
Renter: _______________  Date: _______________'''
                },
                {
                    'title': 'Severance Agreement',
                    'category': 'Business & Employment',
                    'content': '''SEVERANCE AGREEMENT

Date: {date}

Employer: {employer_name}
Employee: {employee_name}

1. TERMINATION DATE
Employment will terminate on {termination_date}.

2. SEVERANCE PAYMENT
The Employer will pay {severance_amount} as severance.

3. BENEFITS CONTINUATION
{benefits_continuation_terms}

4. RELEASE OF CLAIMS
The Employee releases all claims against the Employer.

5. CONFIDENTIALITY
{confidentiality_terms}

Employer: _______________  Date: _______________
Employee: _______________  Date: _______________'''
                },
                {
                    'title': 'Mutual Agreement to Terminate Contract',
                    'category': 'Legal & Personal',
                    'content': '''MUTUAL AGREEMENT TO TERMINATE CONTRACT

Date: {date}

Party 1: {party1_name}
Party 2: {party2_name}

ORIGINAL CONTRACT:
Contract dated: {original_contract_date}
Contract type: {contract_type}

AGREEMENT:
The parties mutually agree to terminate the above contract effective {termination_date}.

SETTLEMENT:
{settlement_terms}

RELEASE:
Both parties release each other from all obligations under the original contract.

Party 1: _______________  Date: _______________
Party 2: _______________  Date: _______________'''
                },
                {
                    'title': 'Catering Services Agreement',
                    'category': 'Services & Freelance',
                    'content': '''CATERING SERVICES AGREEMENT

Date: {date}

Caterer: {caterer_name}
Client: {client_name}

EVENT DETAILS:
Event: {event_name}
Date: {event_date}
Location: {event_location}
Number of Guests: {guest_count}

MENU:
{menu_details}

PRICING:
Total cost: {total_cost}
Payment terms: {payment_terms}

CANCELLATION POLICY:
{cancellation_policy}

Caterer: _______________  Date: _______________
Client: _______________  Date: _______________'''
                },
                {
                    'title': 'Loan Modification Agreement',
                    'category': 'Financial & Loans',
                    'content': '''LOAN MODIFICATION AGREEMENT

Date: {date}

Lender: {lender_name}
Borrower: {borrower_name}

ORIGINAL LOAN:
Original loan amount: {original_loan_amount}
Original loan date: {original_loan_date}

MODIFICATIONS:
New interest rate: {new_interest_rate}
New payment amount: {new_payment_amount}
New payment schedule: {new_payment_schedule}

All other terms of the original loan remain in effect.

Lender: _______________  Date: _______________
Borrower: _______________  Date: _______________'''
                }
            ]
            
            for template_data in templates_data:
                template = Template(**template_data)
                db.session.add(template)
            
            db.session.commit()
            print(f"Database initialized with {len(templates_data)} templates!")

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
