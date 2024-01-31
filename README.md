# Inbox Cleaner

This script helps manage a Gmail inbox by filtering out promotional emails using GPT-3 or GPT-4.

## Prerequisites

- Python 3.7 or higher
- Gmail account
- Google Cloud account with Gmail API enabled
- OpenAI API key

## Setup

1. Clone this repository:

   ```sh
   git clone https://github.com/pszemraj/inbox_cleaner.git
   cd inbox_cleaner
   ```

2. Install the required Python packages:

   ```sh
   pip install -r requirements.txt
   ```

3. Set up your Google API credentials:

   - Follow the instructions [here](https://developers.google.com/workspace/guides/create-credentials) to create a new OAuth 2.0 Client ID.
     - This turns out to be more complicated than it sounds, so there is a helper document [here](SETUP_OAUTH.md) that explains how to do this.
   - Download the JSON file and rename it to `credentials.json`.
   - Put `credentials.json` in the `inbox_cleaner` directory.

4. Set up your OpenAI API key:

   - Follow the instructions [here](https://platform.openai.com/api-keys) to get your OpenAI API key.
   - Set the key as an environment variable:

     ```sh
     export OPENAI_API_KEY=<your_openai_api_key>
     ```

## Usage

Run the script:

```sh
python process_all_unread_emails.py FIRST_NAME LAST_NAME
```

The script will then start processing your unread emails. There will be a log file generated in the `inbox_cleaner` directory named `LOG-process_all_unread_emails.log` - check this file for details on the progress of the script.

### Options

To see the available options, run:

```sh
python process_all_unread_emails.py --help
```

It's worth noting that the default model is set to be `gpt-4-turbo-preview` for future-proofing reasons, but may not always be necessary for your use case, it's worth giving `gpt-3.5-turbo-1106` a try.

---
