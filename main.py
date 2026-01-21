"""Main Gmail Organizer Application"""

import sys
from pathlib import Path
from gmail_auth import GmailAuthManager
from gmail_operations import GmailOperations
from email_classifier import EmailClassifier
from config import BATCH_SIZE, MAX_EMAILS, CATEGORIES


class GmailOrganizer:
    """Main orchestrator for Gmail organization"""

    def __init__(self):
        self.auth_manager = GmailAuthManager()
        self.classifier = EmailClassifier()
        self.accounts = {}
        self.results = {}

    def authenticate_accounts(self, account_names=None):
        """
        Authenticate one or more Gmail accounts

        Args:
            account_names: List of account names, or None to load all
        """
        print("\n=== Gmail Organizer - Account Authentication ===\n")

        if account_names:
            for account_name in account_names:
                try:
                    service, email, name = self.auth_manager.authenticate_account(account_name)
                    self.accounts[name] = {
                        'service': service,
                        'email': email
                    }
                except Exception as e:
                    print(f"Failed to authenticate {account_name}: {e}")
        else:
            # Load all authenticated accounts
            all_accounts = self.auth_manager.load_all_accounts()
            for account_name, (service, email) in all_accounts.items():
                self.accounts[account_name] = {
                    'service': service,
                    'email': email
                }

        print(f"\n✓ Loaded {len(self.accounts)} account(s)")

    def add_new_account(self):
        """Interactive flow to add a new account"""
        print("\n=== Add New Gmail Account ===\n")
        account_name = input("Enter a name for this account (e.g., 'personal', 'work'): ").strip()

        if not account_name:
            print("Account name cannot be empty.")
            return

        try:
            service, email, name = self.auth_manager.authenticate_account(account_name)
            self.accounts[name] = {
                'service': service,
                'email': email
            }
            print(f"\n✓ Added account: {email}")
        except Exception as e:
            print(f"Error adding account: {e}")

    def process_account(self, account_name, max_emails=None, query="in:inbox"):
        """
        Process emails for a single account

        Args:
            account_name: Name of the account to process
            max_emails: Maximum number of emails to process
            query: Gmail search query
        """
        if account_name not in self.accounts:
            print(f"Account '{account_name}' not found.")
            return

        account = self.accounts[account_name]
        service = account['service']
        email = account['email']

        print(f"\n{'='*60}")
        print(f"Processing: {email} ({account_name})")
        print(f"{'='*60}\n")

        # Initialize Gmail operations
        ops = GmailOperations(service, email)

        # Step 1: Create labels
        print("Step 1: Creating Gmail labels...")
        label_map = ops.create_all_labels()

        if not label_map:
            print("Failed to create labels. Aborting.")
            return

        # Step 2: Fetch emails
        print(f"\nStep 2: Fetching emails (query: {query})...")
        total_count = ops.get_email_count(query)
        print(f"Total emails matching query: {total_count}")

        fetch_limit = max_emails or MAX_EMAILS or total_count
        fetch_limit = min(fetch_limit, total_count)

        emails = ops.fetch_emails(max_results=fetch_limit, query=query)

        if not emails:
            print("No emails to process.")
            return

        print(f"Fetched {len(emails)} emails")

        # Step 3: Classify emails
        print(f"\nStep 3: Classifying emails with AI...")
        classified_emails = self.classifier.classify_batch(emails)

        # Step 4: Apply labels
        print(f"\nStep 4: Applying labels to emails...")
        applied_count = 0
        category_counts = {}

        for email in classified_emails:
            category = email['category']
            label_id = label_map.get(category)

            if label_id:
                success = ops.apply_label_to_email(email['email_id'], label_id)
                if success:
                    applied_count += 1
                    category_counts[category] = category_counts.get(category, 0) + 1

            if applied_count % 10 == 0 and applied_count > 0:
                print(f"  Applied {applied_count}/{len(emails)} labels...")

        # Store results
        self.results[account_name] = {
            'email': email,
            'total_processed': len(emails),
            'total_labeled': applied_count,
            'category_counts': category_counts
        }

        # Print summary
        self._print_account_summary(account_name)

    def _print_account_summary(self, account_name):
        """Print summary for a single account"""
        result = self.results.get(account_name)
        if not result:
            return

        print(f"\n{'='*60}")
        print(f"SUMMARY - {result['email']}")
        print(f"{'='*60}")
        print(f"Total emails processed: {result['total_processed']}")
        print(f"Total labels applied: {result['total_labeled']}")
        print(f"\nEmails by category:")

        for category, count in sorted(result['category_counts'].items(), key=lambda x: x[1], reverse=True):
            cat_info = self.classifier.get_category_info(category)
            print(f"  {cat_info['name']}: {count}")

    def print_final_summary(self):
        """Print final summary for all accounts"""
        if not self.results:
            return

        print(f"\n\n{'='*60}")
        print("FINAL SUMMARY - ALL ACCOUNTS")
        print(f"{'='*60}\n")

        total_emails = sum(r['total_processed'] for r in self.results.values())
        total_labeled = sum(r['total_labeled'] for r in self.results.values())

        print(f"Accounts processed: {len(self.results)}")
        print(f"Total emails processed: {total_emails}")
        print(f"Total labels applied: {total_labeled}")

        # Combined category counts
        combined_counts = {}
        for result in self.results.values():
            for category, count in result['category_counts'].items():
                combined_counts[category] = combined_counts.get(category, 0) + count

        if combined_counts:
            print(f"\nCombined category distribution:")
            for category, count in sorted(combined_counts.items(), key=lambda x: x[1], reverse=True):
                cat_info = self.classifier.get_category_info(category)
                percentage = (count / total_emails) * 100
                print(f"  {cat_info['name']}: {count} ({percentage:.1f}%)")

    def run_interactive(self):
        """Interactive CLI mode"""
        print("\n" + "="*60)
        print("  Gmail Organizer - AI-Powered Email Management")
        print("="*60)

        while True:
            print("\nOptions:")
            print("  1. Add new Gmail account")
            print("  2. List authenticated accounts")
            print("  3. Process account emails")
            print("  4. Process all accounts")
            print("  5. Exit")

            choice = input("\nSelect option (1-5): ").strip()

            if choice == "1":
                self.add_new_account()

            elif choice == "2":
                accounts = self.auth_manager.list_authenticated_accounts()
                if accounts:
                    print("\nAuthenticated accounts:")
                    for name, email in accounts:
                        print(f"  - {name}: {email}")
                else:
                    print("\nNo accounts authenticated yet.")

            elif choice == "3":
                accounts = self.auth_manager.list_authenticated_accounts()
                if not accounts:
                    print("\nNo accounts available. Add an account first.")
                    continue

                print("\nAvailable accounts:")
                for i, (name, email) in enumerate(accounts, 1):
                    print(f"  {i}. {name} ({email})")

                try:
                    selection = int(input("\nSelect account number: ")) - 1
                    account_name, _ = accounts[selection]

                    # Load account if not already loaded
                    if account_name not in self.accounts:
                        self.authenticate_accounts([account_name])

                    max_emails = input("Max emails to process (press Enter for all): ").strip()
                    max_emails = int(max_emails) if max_emails else None

                    self.process_account(account_name, max_emails=max_emails)

                except (ValueError, IndexError):
                    print("Invalid selection.")

            elif choice == "4":
                self.authenticate_accounts()
                if not self.accounts:
                    print("\nNo accounts to process.")
                    continue

                max_emails = input("Max emails per account (press Enter for all): ").strip()
                max_emails = int(max_emails) if max_emails else None

                for account_name in self.accounts:
                    self.process_account(account_name, max_emails=max_emails)

                self.print_final_summary()

            elif choice == "5":
                print("\nGoodbye!")
                break

            else:
                print("Invalid option. Try again.")


def main():
    """Main entry point"""
    organizer = GmailOrganizer()

    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        organizer.run_interactive()
    else:
        # Default: run interactive mode
        organizer.run_interactive()


if __name__ == "__main__":
    main()
