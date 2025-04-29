# vAuto Feature Verification System

## Overview

The vAuto Feature Verification System is a tool designed to automate the process of verifying vehicle features in vAuto. It extracts features from window stickers, maps them to vAuto checkboxes, and updates the vehicle records accordingly. This helps ensure that vehicle listings accurately reflect the features present in each vehicle.

## Features

- **Authentication**: Secure login to vAuto with session management
- **Inventory Discovery**: Automatically find vehicles that need feature verification
- **Window Sticker Processing**: Extract features from window sticker PDFs using text extraction and OCR
- **Feature Mapping**: Map extracted features to vAuto checkboxes using fuzzy matching
- **Checkbox Management**: Update vehicle checkboxes in vAuto based on mapped features
- **Reporting**: Generate reports and send email notifications with results

## System Requirements

- Python 3.10 or higher
- Chrome or Firefox browser
- Internet connection
- vAuto account with appropriate permissions

## Installation

1. Clone the repository or extract the ZIP file
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables for credentials:

```bash
# vAuto credentials
export VAUTO_USERNAME="your_username"
export VAUTO_PASSWORD="your_password"

# Email configuration (for reporting)
export SMTP_HOST="smtp.example.com"
export SMTP_PORT="587"
export SMTP_USERNAME="your_email@example.com"
export SMTP_PASSWORD="your_email_password"
export EMAIL_FROM="noreply@example.com"
```

## Configuration

The system is configured using the `configs/config.json` file. You can customize the following settings:

- Browser settings (headless mode, timeout)
- Authentication settings (login URL, session timeout)
- Inventory settings (max vehicles to process, inventory URL)
- Feature mapping settings (confidence threshold)
- Reporting settings (email recipients)

Example configuration:

```json
{
  "browser": {
    "headless": true,
    "timeout": 30
  },
  "authentication": {
    "login_url": "https://app.vauto.com/login",
    "session_timeout_minutes": 60
  },
  "inventory": {
    "max_vehicles": 10,
    "inventory_url": "https://app.vauto.com/inventory"
  },
  "feature_mapping": {
    "confidence_threshold": 0.8
  },
  "reporting": {
    "email_recipients": ["manager@dealership.com"]
  }
}
```

## Usage

### Basic Usage

Run the system with the default configuration:

```bash
python src/main.py
```

### Advanced Usage

Run the system with a specific configuration file:

```bash
python src/main.py --config path/to/config.json
```

Run the system for a specific dealership:

```bash
python src/main.py --dealer "Dealership Name"
```

Run the system for a specific vehicle:

```bash
python src/main.py --vehicle "Stock Number"
```

### Command Line Arguments

- `--config`: Path to configuration file (default: configs/config.json)
- `--dealer`: Dealership name to process
- `--vehicle`: Vehicle stock number to process
- `--debug`: Enable debug logging
- `--no-email`: Disable email notifications
- `--headless`: Run browser in headless mode
- `--no-headless`: Run browser in visible mode

## Architecture

The system follows a modular architecture with clear interfaces and dependency injection:

- **Core**: Contains interfaces, browser automation, and dependency injection container
- **Modules**: Contains the main functionality modules
  - **Authentication**: Handles login and session management
  - **Inventory**: Handles vehicle discovery and checkbox management
  - **Feature Mapping**: Maps extracted features to vAuto checkboxes
  - **Reporting**: Generates reports and sends notifications
- **Utils**: Contains utility functions and helpers

## Development

### Project Structure

```
vauto_manus/
├── configs/                # Configuration files
├── docs/                   # Documentation
├── logs/                   # Log files
├── reports/                # Generated reports
├── src/                    # Source code
│   ├── core/               # Core interfaces and components
│   ├── modules/            # Functional modules
│   │   ├── authentication/ # Authentication module
│   │   ├── inventory/      # Inventory module
│   │   ├── feature_mapping/# Feature mapping module
│   │   └── reporting/      # Reporting module
│   └── utils/              # Utility functions
├── templates/              # Report templates
└── tests/                  # Test suite
    ├── unit/               # Unit tests
    ├── integration/        # Integration tests
    └── fixtures/           # Test fixtures
```

### Running Tests

Run the test suite:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=src
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify your vAuto credentials
   - Check if your account has the necessary permissions
   - Ensure the login URL is correct in the configuration

2. **Browser Automation Issues**
   - Ensure Chrome or Firefox is installed
   - Try running without headless mode for debugging
   - Check if the browser version is compatible with the WebDriver

3. **Feature Extraction Issues**
   - Verify the window sticker PDF is accessible
   - Check if the PDF contains extractable text
   - Adjust the feature mapping confidence threshold

4. **Email Notification Issues**
   - Verify SMTP credentials
   - Check if the SMTP server allows the connection
   - Ensure email recipients are correctly configured

### Logging

The system logs detailed information to the `logs` directory. Check the logs for troubleshooting:

- `vauto.log`: Main application log
- `browser.log`: Browser automation log
- `error.log`: Error log

## Extending the System

### Adding New Feature Mappings

You can add new feature mappings to the `configs/feature_mapping.json` file:

```json
{
  "Feature Name in vAuto": [
    "feature name variant 1",
    "feature name variant 2"
  ]
}
```

### Customizing Report Templates

Report templates are stored in the `templates` directory. You can customize the HTML template to change the report appearance.

### Adding New Modules

To add a new module:

1. Define an interface in `src/core/interfaces.py`
2. Create a new module directory in `src/modules/`
3. Implement the interface in your module
4. Register the module in the dependency injection container in `src/core/container.py`
5. Add tests for your module in `tests/unit/`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please contact the development team or open an issue in the repository.
