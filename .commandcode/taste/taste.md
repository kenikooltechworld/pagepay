# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# workflow
- Before writing code for business logic decisions (e.g., revenue calculations, ad payout rates, user earnings math), first research thoroughly via web search and present findings to the user for confirmation before making any changes. Do not assume values, rush into implementation, or push code — discuss and align first. Confidence: 0.82

# architecture
- Points earning model is purely ad-driven: users earn points only from pre-read and post-read ad views (80% of ad revenue, converted via live FX rate at 100 pts = ₦1), NOT from reading time or session duration. No reading-time bonuses apply. Confidence: 0.85
- Remove the `/session/claim` call and the reading-time point formula (`(effective_duration // 600) * 5`) from the session flow — points should come exclusively from ad revenue, not reading duration. Confidence: 0.80
- Ad revenue passed to the backend must come from AdMob's actual payout (e.g., SSV callback), not hardcoded `revenueUsd: 0.01` in `RewardedAd.tsx`. Confidence: 0.80

