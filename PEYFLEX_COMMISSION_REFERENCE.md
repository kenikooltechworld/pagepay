# Peyflex Commission Quick Reference

**Your Current Tier**: Free API (₦0/year)  
**Upgrade Option**: Top Reseller (₦5,000/year)  
**Points System**: 10 points = ₦1

---

## Commission Rates by Service

### Data Bundles

| Service | Free API | Top Reseller | Notes |
|---------|----------|--------------|-------|
| **MTN Shared Data** | 3% | **6%** 🔥 | Highest commission - promote this! |
| MTN Gifting Data | 0.5% | 1% | Lower than shared |
| Airtel Gifting | 0.5% | 1% | |
| Airtel Awoof | 0.5% | 1% | |
| Glo Data (CG) | 1% | 2% | Corporate Gifting |
| 9mobile Data (CG) | 1% | 2% | Corporate Gifting |
| All Corporate Gifting | 1% | 2% | |
| All Gifting Plans | 0.5% | 1% | |

### Airtime

| Network | Free API | Top Reseller |
|---------|----------|--------------|
| MTN | 1% | 2% |
| Airtel | 1% | 2% |
| Glo | 1% | 2% |
| 9mobile | 1% | 2% |

### Utilities

| Service | Free API | Top Reseller |
|---------|----------|--------------|
| All Electricity DISCOs | 0.1% | 0.5% |
| GOtv | 0.1% | 0.5% |
| DStv | 0.1% | 0.5% |
| Startimes | 0.5% | 1% |

### Other Services

| Service | Free API | Top Reseller |
|---------|----------|--------------|
| Betting (All) | 0.01% | 0.05% |
| Recharge Card Printing | Fixed per card | Fixed per card |

---

## Real Money Examples

### Free API Tier (Current)

**MTN Shared Data ₦1,000**:
- Commission: ₦30 (3%)
- User earns: 201 points = **₦20.10**
- Platform keeps: **₦9.90**

**MTN Airtime ₦100**:
- Commission: ₦1 (1%)
- User earns: 67 points = **₦0.67**
- Platform keeps: **₦0.33**

**Electricity ₦5,000**:
- Commission: ₦5 (0.1%)
- User earns: 335 points = **₦3.35**
- Platform keeps: **₦1.65**

**DStv ₦4,400**:
- Commission: ₦4.40 (0.1%)
- User earns: 295 points = **₦2.95**
- Platform keeps: **₦1.45**

---

### Top Reseller Tier (After ₦5,000 Upgrade)

**MTN Shared Data ₦1,000**:
- Commission: ₦60 (6%) 🚀
- User earns: 4,020 points = **₦40.20** (2x more!)
- Platform keeps: **₦19.80** (2x more!)

**MTN Airtime ₦100**:
- Commission: ₦2 (2%) 🚀
- User earns: 134 points = **₦1.34**
- Platform keeps: **₦0.66**

**Electricity ₦5,000**:
- Commission: ₦25 (0.5%) 🚀
- User earns: 1,675 points = **₦16.75** (5x more!)
- Platform keeps: **₦8.25** (5x more!)

**DStv ₦4,400**:
- Commission: ₦22 (0.5%) 🚀
- User earns: 1,474 points = **₦14.74** (5x more!)
- Platform keeps: **₦7.26** (5x more!)

---

## When to Upgrade?

### Break-Even Analysis

**Upgrade Cost**: ₦5,000/year = ₦417/month

**Monthly Volume Needed**:
```
If you process ₦100,000/month in bills:
- Free API profit: ~₦2,000/month
- Top Reseller profit: ~₦4,000/month
- Extra profit: ₦2,000/month
- ROI: (₦2,000 - ₦417) = ₦1,583/month net gain ✅

Upgrade break-even: ₦25,000/month bills volume
```

### Recommendation

| Monthly Bills Volume | Action |
|---------------------|--------|
| < ₦25,000 | Stay on Free API |
| ₦25,000 - ₦50,000 | Consider upgrade |
| ₦50,000 - ₦100,000 | Upgrade recommended |
| > ₦100,000 | **Upgrade immediately** 🚀 |

---

## User Marketing Strategy

### For Free API Tier
"**Earn cashback on every bill!**"
- MTN Data: Earn up to 4% back
- Airtime: Earn 1% back  
- Electricity: Earn 0.2% back

### After Top Reseller Upgrade
"**DOUBLED CASHBACK!**"
- MTN Data: Now earn up to **8%** back! 🔥
- Airtime: Now earn **2%** back!
- Electricity: Now earn **1%** back!

---

## Pro Tips

### 1. Promote High-Commission Services
Focus marketing on:
- **MTN Shared Data** (3-6% commission)
- **Corporate Gifting Data** (1-2% commission)
- Airtime is good for volume but lower margin

### 2. Track Your Volume
Monitor `BillTransaction` table:
```sql
-- Monthly volume
SELECT 
  SUM(amount_naira) as total_volume,
  SUM(commission_naira) as total_commission,
  SUM(points_earned) as user_share,
  COUNT(*) as transactions
FROM bill_transactions
WHERE created_at >= DATE_TRUNC('month', NOW());
```

### 3. Optimize for Shared Data
MTN Shared Data has 2x the commission of gifting. Educate users:
- "Shared Data gives you MORE cashback"
- Show comparison in UI
- Default selection to shared when available

### 4. Plan Upgrade Timing
- Wait until you hit ₦100,000/month volume
- Upgrade at month start to maximize value
- Announce "DOUBLED CASHBACK" to users same day

---

## Support & Contact

**Peyflex Support**:
- WhatsApp: Contact via Peyflex dashboard
- Email: support@peyflex.com.ng
- Response time: Usually same day

**Upgrade Process**:
1. Log into Peyflex dashboard
2. Go to "Upgrade Account"
3. Pay ₦5,000 (one-time, yearly)
4. Account upgraded instantly
5. **Your app automatically uses new rates** (no code changes!)

---

## Key Takeaways

✅ Commission comes from Peyflex's real API response  
✅ Users get 67% of commission as points  
✅ Platform keeps 33% as profit  
✅ Upgrade doubles most commissions  
✅ No code changes needed after upgrade  
✅ System is fully automatic and safe  

**Your bills system is now production-ready!** 🚀
