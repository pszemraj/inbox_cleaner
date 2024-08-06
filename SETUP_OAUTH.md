
# OAuth 2.0 Setup Guide for Gmail API Access

## Introduction

This document provides a step-by-step guide to setting up OAuth 2.0 credentials for a desktop application that needs to access the Gmail API to manage a user's inbox.

## Google Cloud Project Setup

1. **Create a Google Cloud Project**:
   - Visit [Google Cloud Console](https://console.cloud.google.com/).
   - Create a new project or select an existing one.

2. **Enable the Gmail API**:
   - Navigate to "APIs & Services > Dashboard".
   - Click "+ ENABLE APIS AND SERVICES".
   - Search for "Gmail API" and enable it.

## OAuth Consent Screen Configuration

1. **Configure the OAuth Consent Screen**:
   - Go to "APIs & Services > OAuth consent screen".
   - Choose the user type (External or Internal).
   - Fill in the application details (app name, support email, etc.).

2. **Add Scopes**:
   - Click "ADD OR REMOVE SCOPES".
   - Search for the `https://www.googleapis.com/auth/gmail.modify` scope and select it.
   - Provide a user-facing description explaining why your app needs this access.

## Creating OAuth Client ID Credentials

1. **Create Credentials**:
   - Go to "APIs & Services > Credentials".
   - Click "Create credentials" and select "OAuth client ID".
   - Choose "Desktop app" as the application type.
   - Enter a name and proceed.

2. **Download Credentials**:
   - Download the credentials JSON file once the client ID is created.
   - Save this file as `credentials.json` in your application's directory.
   - then you can run the script.

> [!IMPORTANT]
> When returning to this repo down the road, make sure to remove the generated `token.json` file before running the script again. (it will be regenerated again and prompt you)

## Testing and Verification

1. **Add Test Users**:
   - On the "Test users" tab, click "+ ADD USERS".
   - Enter the email addresses of the Google accounts you want to authorize for testing.
   - Save the changes.

2. **Test Your Application**:
   - Execute your script or application.
   - Authenticate using one of the test user accounts.
   - Grant the necessary permissions via the consent screen.

## Going Live

1. **Submit for Verification** (if using sensitive scopes):
   - Once you're ready to go live, submit your OAuth consent screen for Google's verification process.
   - This step is mandatory for applications that need to be available to users outside your organization.

2. **Remove Testing Restrictions**:
   - After passing verification, you can allow all users to authenticate with your application.

## Best Practices

- Adhere to Google's security and privacy guidelines.
- Only request the scopes necessary for your application's functionality.
- Keep your `credentials.json` and `token.json` files secure and do not expose them publicly.

---
