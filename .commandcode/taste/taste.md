# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# workflow
- When the user provides API credentials (API keys, docs URLs, etc.) for a real service, use the actual API endpoints/data — do not create hardcoded placeholder/mock data as a substitute. The API credentials are provided specifically so the real service is used, not simulated. Confidence: 0.85

# workflow
- When adding new components to existing screen files (e.g., wallet.tsx), always verify the required React Native imports (TouchableOpacity, etc.) are included — the error `Property 'TouchableOpacity' doesn't exist` means an import was missed. Confidence: 0.70
- Before writing code for business logic decisions (e.g., revenue calculations, ad payout rates, user earnings math), first research thoroughly via web search and present findings to the user for confirmation before making any changes. Do not assume values, rush into implementation, or push code — discuss and align first. Confidence: 0.82
- Before coding new screens or features, first present a visual design/mockup for the user to review and approve. Do not jump straight into implementation code. Confidence: 0.70

# architecture
See [architecture/taste.md](architecture/taste.md)

# monetization
- For user rewards and platform revenue, use third-party affiliate integrations (e.g., airtime/data/electricity bill payments via aggregator APIs) where the third party pays the commission. Split commission between user points and platform profit — never fund user rewards from the platform's own pocket. Confidence: 0.70
- Never display the platform's earnings/cut/margin to end users in any UI mockup or screen. The commission split between user and platform must remain invisible to users — only show what the user earns (points), not what the platform keeps. Confidence: 0.75
- Use Peyflex as the primary VTU/data/airtime aggregator API, with other providers (e.g., VTpass) as fallback. Peyflex offers free API access and better data margins (5% discount). The base URL is `https://client.peyflex.com.ng` and authentication uses `Authorization: Token <api_key>` header. Confidence: 0.70
