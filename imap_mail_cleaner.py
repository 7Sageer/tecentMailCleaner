#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IMAP Mail Cleaner

This script connects to an IMAP mail server and deletes emails older than a specified date.
It can be configured to target specific folders and has safety features to prevent accidental deletion.
It can also delete emails within a specific time range (down to the minute).
"""

import imaplib
import email
import email.utils
import datetime
import argparse
import getpass
import sys
import logging
from typing import List, Optional, Tuple
import time
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class IMAPMailCleaner:
    """Class to handle the cleaning of old emails from an IMAP mailbox."""
    
    def __init__(
        self, 
        server: str, 
        username: str, 
        password: str, 
        port: int = 993, 
        use_ssl: bool = True
    ):
        """
        Initialize the IMAP connection.
        
        Args:
            server: IMAP server address
            username: Email account username
            password: Email account password
            port: IMAP server port (default: 993)
            use_ssl: Whether to use SSL connection (default: True)
        """
        self.server = server
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.conn = None
    
    def connect(self) -> bool:
        """
        Connect to the IMAP server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.use_ssl:
                self.conn = imaplib.IMAP4_SSL(self.server, self.port)
            else:
                self.conn = imaplib.IMAP4(self.server, self.port)
                
            self.conn.login(self.username, self.password)
            logger.info(f"Successfully connected to {self.server} as {self.username}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {e}")
            return False
    
    def disconnect(self):
        """Close the IMAP connection."""
        if self.conn:
            try:
                self.conn.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
    
    def list_folders(self) -> List[str]:
        """
        List all available folders/mailboxes.
        
        Returns:
            List[str]: List of folder names
        """
        if not self.conn:
            logger.error("Not connected to IMAP server")
            return []
        
        try:
            status, folder_list = self.conn.list()
            if status != 'OK':
                logger.error(f"Failed to list folders: {status}")
                return []
            
            folders = []
            for folder in folder_list:
                if isinstance(folder, bytes):
                    # Decode and extract folder name
                    decoded = folder.decode('utf-8')
                    # Extract the folder name (typically the last quoted part)
                    parts = decoded.split('"')
                    if len(parts) >= 2:
                        folder_name = parts[-2]
                        folders.append(folder_name)
            
            return folders
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []
    
    def select_folder(self, folder: str) -> int:
        """
        Select a folder/mailbox to work with.
        
        Args:
            folder: Name of the folder to select
            
        Returns:
            int: Number of messages in the folder, -1 if error
        """
        if not self.conn:
            logger.error("Not connected to IMAP server")
            return -1
        
        try:
            status, data = self.conn.select(folder)
            if status != 'OK':
                logger.error(f"Failed to select folder '{folder}': {status}")
                return -1
            
            message_count = int(data[0])
            logger.info(f"Selected folder '{folder}' with {message_count} messages")
            return message_count
        except Exception as e:
            logger.error(f"Error selecting folder '{folder}': {e}")
            return -1
    
    def search_old_messages(self, days_old: int) -> List[str]:
        """
        Search for messages older than the specified number of days.
        
        Args:
            days_old: Number of days to use as threshold
            
        Returns:
            List[str]: List of message IDs older than the threshold
        """
        if not self.conn:
            logger.error("Not connected to IMAP server")
            return []
        
        try:
            # Calculate the date threshold
            cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_old)).strftime("%d-%b-%Y")
            
            # Search for messages older than the cutoff date
            status, data = self.conn.search(None, f'BEFORE {cutoff_date}')
            
            if status != 'OK':
                logger.error(f"Failed to search for old messages: {status}")
                return []
            
            # Get the list of message IDs
            message_ids = data[0].split()
            return [msg_id.decode('utf-8') for msg_id in message_ids]
        except Exception as e:
            logger.error(f"Error searching for old messages: {e}")
            return []
    
    def search_messages_in_timerange(self, start_time: datetime.datetime, end_time: datetime.datetime) -> List[str]:
        """
        Search for messages within a specific time range.
        
        Args:
            start_time: Start time of the range (inclusive)
            end_time: End time of the range (inclusive)
            
        Returns:
            List[str]: List of message IDs within the time range
        """
        if not self.conn:
            logger.error("Not connected to IMAP server")
            return []
        
        try:
            # Format dates for IMAP search
            start_date = start_time.strftime("%d-%b-%Y")
            end_date = end_time.strftime("%d-%b-%Y")
            
            # Search for messages in the date range
            status, data = self.conn.search(None, f'SINCE {start_date} BEFORE {end_date}')
            
            if status != 'OK':
                logger.error(f"Failed to search for messages in time range: {status}")
                return []
            
            # Get the list of message IDs
            message_ids = data[0].split()
            message_ids = [msg_id.decode('utf-8') for msg_id in message_ids]
            
            # Further filter by time (IMAP SEARCH doesn't support time, only dates)
            filtered_ids = []
            for msg_id in message_ids:
                subject, sender, date_str = self.get_message_info(msg_id)
                
                # Try to parse the email date
                try:
                    # Parse the date from email header
                    parsed_date = email.utils.parsedate_to_datetime(date_str)
                    
                    # Check if it's within our time range
                    if start_time <= parsed_date <= end_time:
                        filtered_ids.append(msg_id)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Could not parse date '{date_str}' for message ID {msg_id}: {e}")
                    continue
            
            return filtered_ids
        except Exception as e:
            logger.error(f"Error searching for messages in time range: {e}")
            return []
    
    def get_message_info(self, msg_id: str) -> Tuple[str, str, str]:
        """
        Get basic information about a message.
        
        Args:
            msg_id: Message ID
            
        Returns:
            Tuple[str, str, str]: (subject, from, date) of the message
        """
        if not self.conn:
            logger.error("Not connected to IMAP server")
            return ("", "", "")
        
        try:
            status, data = self.conn.fetch(msg_id, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])')
            if status != 'OK':
                logger.error(f"Failed to fetch message {msg_id}: {status}")
                return ("", "", "")
            
            if not data or not data[0]:
                return ("", "", "")
            
            # Parse the email header
            msg = email.message_from_bytes(data[0][1])
            subject = msg.get('Subject', 'No Subject')
            sender = msg.get('From', 'Unknown Sender')
            date = msg.get('Date', 'Unknown Date')
            
            return (subject, sender, date)
        except Exception as e:
            logger.error(f"Error getting message info for {msg_id}: {e}")
            return ("", "", "")
    
    def delete_messages(self, message_ids: List[str], dry_run: bool = True) -> int:
        """
        Delete the specified messages.
        
        Args:
            message_ids: List of message IDs to delete
            dry_run: If True, only simulate deletion (default: True)
            
        Returns:
            int: Number of messages deleted
        """
        if not self.conn:
            logger.error("Not connected to IMAP server")
            return 0
        
        if not message_ids:
            logger.info("No messages to delete")
            return 0
        
        deleted_count = 0
        
        try:
            for msg_id in message_ids:
                subject, sender, date = self.get_message_info(msg_id)
                
                if dry_run:
                    logger.info(f"Would delete: ID: {msg_id}, Subject: {subject}, From: {sender}, Date: {date}")
                    deleted_count += 1
                else:
                    # Mark the message for deletion
                    self.conn.store(msg_id, '+FLAGS', '\\Deleted')
                    logger.info(f"Marked for deletion: ID: {msg_id}, Subject: {subject}, From: {sender}, Date: {date}")
                    deleted_count += 1
            
            if not dry_run:
                # Permanently remove messages marked for deletion
                self.conn.expunge()
                logger.info(f"Expunged {deleted_count} messages")
            
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting messages: {e}")
            return deleted_count


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Clean old emails from IMAP mailbox')
    
    parser.add_argument('--server', required=True, help='IMAP server address')
    parser.add_argument('--port', type=int, default=993, help='IMAP server port (default: 993)')
    parser.add_argument('--username', required=True, help='Email account username')
    parser.add_argument('--password', help='Email account password (will prompt if not provided)')
    parser.add_argument('--no-ssl', action='store_true', help='Disable SSL connection')
    
    parser.add_argument('--folder', default='INBOX', help='Folder to clean (default: INBOX)')
    parser.add_argument('--list-folders', action='store_true', help='List available folders and exit')
    
    # Time range options
    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument('--days', type=int, default=30, help='Delete emails older than this many days (default: 30)')
    time_group.add_argument('--time-range', nargs=2, metavar=('START', 'END'),
                           help='Delete emails within time range (format: YYYY-MM-DD HH:MM or YYYY-MM-DD)')
    
    parser.add_argument('--dry-run', action='store_true', help='Simulate deletion without actually deleting')
    
    return parser.parse_args()


def parse_time_str(time_str: str) -> datetime.datetime:
    """
    Parse time string into datetime object.
    
    Args:
        time_str: Time string in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'
        
    Returns:
        datetime.datetime: Parsed datetime object
        
    Raises:
        ValueError: If the time string format is invalid
    """
    # Try to parse with time
    try:
        if ' ' in time_str:
            return datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        else:
            # If only date is provided, set time to 00:00
            return datetime.datetime.strptime(time_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str}. Expected format: 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'")


def main():
    """Main function to run the script."""
    args = parse_arguments()
    
    # Prompt for password if not provided
    password = args.password
    if not password:
        password = getpass.getpass(f"Enter password for {args.username}: ")
    
    # Create the cleaner instance
    cleaner = IMAPMailCleaner(
        server=args.server,
        username=args.username,
        password=password,
        port=args.port,
        use_ssl=not args.no_ssl
    )
    
    # Connect to the server
    if not cleaner.connect():
        sys.exit(1)
    
    try:
        # List folders if requested
        if args.list_folders:
            folders = cleaner.list_folders()
            if folders:
                logger.info("Available folders:")
                for folder in folders:
                    print(f"  - {folder}")
            else:
                logger.warning("No folders found or unable to list folders")
            return
        
        # Select the folder
        message_count = cleaner.select_folder(args.folder)
        if message_count < 0:
            logger.error(f"Failed to select folder: {args.folder}")
            return
        
        # Determine which search method to use based on arguments
        if args.time_range:
            try:
                start_time = parse_time_str(args.time_range[0])
                end_time = parse_time_str(args.time_range[1])
                
                # Make sure start time is before end time
                if start_time > end_time:
                    logger.error("Start time must be before end time")
                    return
                
                logger.info(f"Searching for emails between {start_time} and {end_time}")
                messages = cleaner.search_messages_in_timerange(start_time, end_time)
                logger.info(f"Found {len(messages)} messages in the specified time range")
            except ValueError as e:
                logger.error(f"Error parsing time range: {e}")
                return
        else:
            # Use the default days-based search
            messages = cleaner.search_old_messages(args.days)
            logger.info(f"Found {len(messages)} messages older than {args.days} days")
        
        # Delete found messages
        if messages:
            deleted = cleaner.delete_messages(messages, dry_run=args.dry_run)
            if args.dry_run:
                logger.info(f"Dry run: Would have deleted {deleted} messages")
            else:
                logger.info(f"Successfully deleted {deleted} messages")
        else:
            if args.time_range:
                logger.info(f"No messages found in the specified time range in {args.folder}")
            else:
                logger.info(f"No messages older than {args.days} days found in {args.folder}")
    
    finally:
        # Always disconnect
        cleaner.disconnect()


if __name__ == "__main__":
    main()