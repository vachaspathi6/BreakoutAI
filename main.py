import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import re  # For time format validation
import openai
from mailjet_rest import Client
import requests
import json
import uuid
import os
import pyperclip  # To copy content to clipboard

# Sidebar: Page Navigation
st.title("Custom Email Sender Application")

# Sidebar: User email and password for authentication
st.sidebar.header("User Authentication")
email_address = st.sidebar.text_input("Email Address")
email_password = st.sidebar.text_input("Password (Use App Password)", type="password")

# Sidebar: OpenAI API Key input
st.sidebar.header("OpenAI API Key")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")

# Streamlit Sidebar for Mailjet API Credentials
st.sidebar.header("Mailjet API Credentials")
mailjet_api_key = st.sidebar.text_input("Mailjet API Key", type="password")
mailjet_api_secret = st.sidebar.text_input("Mailjet API Secret", type="password")


# Sidebar: File upload
st.sidebar.header("Upload Recipients File")
uploaded_file = st.sidebar.file_uploader("Upload CSV or XLSX file", type=['csv', 'xlsx'])

# Function to load and display the uploaded dataset
def load_data(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file, engine='openpyxl')

        return df
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

# Main Screen: Display the uploaded file content
if uploaded_file:
    df = load_data(uploaded_file)
    if df is not None:
        st.write("Recipient Data Preview:")
        st.dataframe(df)

        # Verify the file contains an 'email' column
        if 'email' not in df.columns:
            st.error("The uploaded file must contain an 'email' column.")

        # Email Subject and Message Customization
        subject = st.text_input("Email Subject")

        # Add a prompt box to generate the email message dynamically using OpenAI
        st.subheader("Generate Email Body with OpenAI (Optional)")

        prompt = st.text_area("Enter your prompt to generate the email body:")
        if st.button("Generate Email Body"):
            if openai_api_key:
                openai.api_key = openai_api_key  # Set OpenAI API Key

                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=500,  # Set the limit on the response length
                        temperature=0.7
                    )
                    generated_message = response.choices[0].message['content'].strip()
                    st.session_state.generated_message = generated_message  # Store in session state
                    message_body = generated_message  # Update message body with the generated response
                    st.success("Generated email body using OpenAI")
                    st.text_area("Generated Email Body", value=generated_message, height=100)

                except Exception as e:
                    st.error(f"Error generating email body with OpenAI: {e}")
            else:
                st.error("Please enter your OpenAI API key to generate the email body.")
        
        # Copy Button to copy generated email content to clipboard
        if "generated_message" in st.session_state:
            if st.button("Copy"):
                pyperclip.copy(st.session_state.generated_message)
                st.success("Email body copied to clipboard!")

        # Email Message field
        message_body = st.text_area("Email Message")

        # Optional file attachment
        st.header("Optional: Upload an Attachment")
        attachment_file = st.file_uploader("Choose a file to attach")

        # Ensure the user provides the API credentials
        if not mailjet_api_key or not mailjet_api_secret:
            st.error("Please enter your Mailjet API Key and Secret in the sidebar.")
        else:
            # Initialize Mailjet client with provided credentials
            mailjet = Client(auth=(mailjet_api_key, mailjet_api_secret), version='v3.1')

        # Schedule Email Sending and Throttling Email Sending Sections Side by Side
        st.write("----")  # Divider line

        # Create two columns for Schedule and Throttling sections
        col1, col2 = st.columns(2)

        # Track email statuses
        total_emails = len(df)
        emails_sent = 0
        emails_pending = 0
        total_emails = 0
        emails_failed = 0
        response_rate = 0  # Placeholder, requires tracking
        email_statuses = []

        # Initialize session state for email statuses
        if "email_statuses" not in st.session_state:
            st.session_state["email_statuses"] = []

        # Schedule Email Sending Section
        with col1:
            st.header("Schedule Email Sending (Optional)")
            scheduled_date = st.date_input("Select a Date", min_value=datetime.today().date())
            scheduled_time = st.text_input("Enter Time in HH:MM (24-hour format)")

            # Validate time input
            time_pattern = re.compile(r"^(2[0-3]|[01]?[0-9]):([0-5]?[0-9])$")
            if scheduled_time and not time_pattern.match(scheduled_time):
                st.error("Invalid time format. Please enter time in HH:MM format.")
            else:
                # "Send Emails" button
                if st.button("Send Emails"):
                    if email_address and email_password:
                        try:
                            # Combine date and time for scheduling if valid
                            if scheduled_time:
                                scheduled_datetime = datetime.combine(scheduled_date, datetime.strptime(scheduled_time, "%H:%M").time())
                            else:
                                scheduled_datetime = datetime.now()  # Send immediately if no time specified

                            # Check if the scheduled time is in the future
                            current_time = datetime.now()
                            if scheduled_datetime > current_time:
                                time_until_send = (scheduled_datetime - current_time).total_seconds()
                                st.info(f"Scheduling emails to be sent in {timedelta(seconds=time_until_send)}.")
                                time.sleep(time_until_send)  # Wait until the scheduled time

                            # Loop over each recipient
                            for index, row in df.iterrows():
                                company_name = row['company_name']
                                recipient_email = row['email']

                                tracking_url = f"http://127.0.0.1:5001/track/{recipient_email}"


                                # Personalize the subject dynamically by replacing placeholders
                                personalized_subject = subject
                                personalized_message = f"{message_body}<br><img src='{tracking_url}' alt='' style='display:none;'>"

                                for column in df.columns:
                                    placeholder = f"{{{{{column}}}}}"
                                    value = row.get(column, '')
                                    personalized_subject = personalized_subject.replace(placeholder, str(value))
                                    personalized_message = personalized_message.replace(placeholder, str(value))

                                # Prepare the Mailjet email payload
                                data = {
                                    'Messages': [
                                        {
                                            "From": {
                                                "Email": email_address,
                                                "Name": "Suraj Kumar"
                                            },
                                            "To": [
                                                {
                                                    "Email": recipient_email
                                                }
                                            ],
                                            "Subject": personalized_subject,
                                            "HTMLPart": personalized_message,
                                            "Attachments": [],
                                            "TrackOpens": "enabled"
                                        }
                                    ]
                                }

                                # Update the session state
                                st.session_state["email_statuses"].append([company_name, recipient_email, "Scheduled", "N/A", "No"])

                                # Send email
                                try:
                                    result = mailjet.send.create(data=data)
                                    if result.status_code == 200:
                                        st.session_state["email_statuses"][-1][2] = "Sent"
                                        st.session_state["email_statuses"][-1][3] = "Delivered"
                                    else:
                                        st.session_state["email_statuses"][-1][2] = "Failed"
                                        st.session_state["email_statuses"][-1][3] = "Bounced"
                                except Exception as e:
                                    st.session_state["email_statuses"][-1][2] = "Failed"
                                    st.session_state["email_statuses"][-1][3] = "Bounced"

                                
                            st.success("Emails sent successfully!")

                            # Save to session state
                            st.session_state["email_statuses"].extend(email_statuses)

                        except Exception as e:
                            st.error(f"An error occurred: {e}")
                    else:
                        st.error("Please enter your email and app password to send emails.")

        
        # Display a vertical line using CSS
        st.markdown(
            """
            <style>
            div[data-testid="column"]:nth-child(2) {
                border-right: 1px solid #d3d3d3;
                height: 100%;
                margin: 0 15px;
            }
            </style>
            """, 
            unsafe_allow_html=True
        )

        # Throttling Email Sending Section
        with col2:
            st.header("Throttling Email Sending (Optional)")
            emails_per_minute = st.number_input("Emails per Minute", min_value=0, max_value=60, value=10)
            emails_per_hour = st.number_input("Emails per Hour", min_value=0, max_value=1000, value=100)
            throttle_rate = 60 / emails_per_minute  # Calculate time in seconds per email

            # "Send Emails with Throttling" button
            if st.button("Send with Throttling"):
                if email_address and email_password:
                    try:
                        # Loop over each recipient with throttling
                        for index, row in df.iterrows():
                            company_name = row['company_name']
                            recipient_email = row['email']

                            tracking_url = f"http://127.0.0.1:5001/track/{recipient_email}"

                            # Personalize the subject & message dynamically by replacing placeholders
                            personalized_subject = subject
                            personalized_message = f"{message_body}<br><img src='{tracking_url}' alt='' style='display:none;'>"

                            for column in df.columns:
                                placeholder = f"{{{{{column}}}}}"  
                                value = row.get(column, '') 
                                personalized_subject = personalized_subject.replace(placeholder, str(value))
                                personalized_message = personalized_message.replace(placeholder, str(value))

                            # Prepare the Mailjet email payload
                            data = {
                                'Messages': [
                                    {
                                        "From": {
                                        "Email": email_address,
                                        "Name": "Suraj Kumar"
                                    },
                                    "To": [
                                        {
                                            "Email": recipient_email
                                        }
                                    ],
                                    "Subject": personalized_subject,
                                    "HTMLPart": personalized_message,
                                    "Attachments": [],
                                    "TrackOpens": "enabled"
                                    }
                                ]
                            }

                            # Update the session state
                            st.session_state["email_statuses"].append([company_name, recipient_email, "Scheduled", "N/A", "No"])

                            # Send email
                            try:
                                result = mailjet.send.create(data=data)
                                if result.status_code == 200:
                                    st.session_state["email_statuses"][-1][2] = "Sent"
                                    st.session_state["email_statuses"][-1][3] = "Delivered"
                                else:
                                    st.session_state["email_statuses"][-1][2] = "Failed"
                                    st.session_state["email_statuses"][-1][3] = "Bounced"
                            except Exception as e:
                                st.session_state["email_statuses"][-1][2] = "Failed"
                                st.session_state["email_statuses"][-1][3] = "Bounced"
                            
                            # Introduce delay for throttling
                            time.sleep(throttle_rate)

                        st.success("Emails sent successfully with throttling!")

                        # Save to session state
                        st.session_state["email_statuses"].extend(email_statuses)
                            
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                else:
                    st.error("Please enter your email and app password to send emails.")


        st.write("----")
        # Real-Time Analytics
        st.subheader("Real-Time Analytics")
        total_emails = len(st.session_state["email_statuses"])
        emails_sent = sum(1 for status in st.session_state["email_statuses"] if status[2] == "Sent")
        emails_failed = sum(1 for status in st.session_state["email_statuses"] if status[2] == "Failed")
        emails_pending = total_emails - emails_sent - emails_failed
        
        # Calculate the number of opened emails
        emails_opened = sum(1 for status in st.session_state["email_statuses"] if status[4] == "Yes")

        # Calculate total number of emails sent (already computed)
        emails_sent = sum(1 for status in st.session_state["email_statuses"] if status[2] == "Sent")

        # Calculate response rate (opened emails / sent emails)
        response_rate = 0
        if emails_sent > 0:
            response_rate = (emails_opened / emails_sent) * 100

        # Show the result
        st.write(f"Response Rate: {response_rate:.2f}%")

        analytics_data = {
            "Metric": ["Total Emails Sent", "Emails Pending", "Emails Failed", "Response Rate"],
            "Value": [emails_sent, emails_pending, emails_failed, f"{response_rate}%"],
        }
        analytics_df = pd.DataFrame(analytics_data)
        st.table(analytics_df)

        st.write("----")
        # Real-Time Dashboard
        st.subheader("Real-Time Dashboard")

        if st.button("Refresh Dashboard"):
            try:
                # Sync opened emails with the dashboard
                for status in st.session_state["email_statuses"]:
                    if status[1] in opened_emails:
                        status[4] = "Yes"  # Mark as opened
                    else:
                        status[4] = "No"  # If not opened, keep it as "No"

                # Refresh the dashboard
                dashboard_df = pd.DataFrame(
                    st.session_state["email_statuses"],
                    columns=["Company Name", "Email", "Status", "Delivery Status", "Opened"],
                )
                st.table(dashboard_df)

            except Exception as e:
                st.error(f"Error refreshing dashboard: {e}")

    else:
        st.error("No valid data found in the uploaded file.")


