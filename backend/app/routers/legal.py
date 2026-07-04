from datetime import datetime, timezone
from fastapi import APIRouter
from app.schemas import LegalPageResponse

router = APIRouter(prefix="/legal", tags=["legal"])

TERMS_CONTENT = """PagePay Terms of Service

1. Acceptance of Terms
By accessing or using PagePay, you agree to be bound by these Terms.

2. Eligibility
You must be at least 13 years old and have the legal capacity to enter into these Terms.

3. Accounts
You are responsible for maintaining the confidentiality of your account credentials.

4. Tasks and Payments
Sponsors fund task rewards in escrow. Workers earn rewards by completing tasks according to sponsor instructions.
PagePay deducts a 15% platform fee before crediting rewards.

5. Prohibited Activities
Fraud, duplicate accounts, fake submissions, or abuse of the referral system may result in account suspension.

6. Termination
We reserve the right to suspend or terminate accounts that violate these Terms.

7. Changes
We may update these Terms from time to time. Continued use constitutes acceptance of the revised Terms.
"""

PRIVACY_CONTENT = """PagePay Privacy Policy

1. Information We Collect
We collect information you provide directly (email, phone, profile data) and usage data (task activity, device info).

2. How We Use Information
We use your data to operate the platform, process payments, prevent fraud, and improve user experience.

3. Data Sharing
We do not sell your personal data. We share data with trusted service providers (payment processors, cloud hosting) as necessary.

4. Security
We implement industry-standard security measures including encrypted authentication and secure database storage.

5. Your Rights
You may request access to or deletion of your personal data by contacting support@pagepay.ng.

6. Children's Privacy
PagePay does not knowingly collect data from children under 13.

7. Contact
For privacy questions, contact support@pagepay.ng.
"""


@router.get("/terms", response_model=LegalPageResponse)
async def get_terms():
    return LegalPageResponse(
        slug="terms",
        title="Terms of Service",
        content=TERMS_CONTENT,
        updated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


@router.get("/privacy", response_model=LegalPageResponse)
async def get_privacy():
    return LegalPageResponse(
        slug="privacy",
        title="Privacy Policy",
        content=PRIVACY_CONTENT,
        updated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
