"""One-shot script: fix sponsor.py PaystackClient() bug and
fraud_detection.py User.device_fingerprint bug."""

# 1. sponsor.py
sp_path = r'C:\Users\kenik\OneDrive\Desktop\pagepay\backend\app\routers\sponsor.py'
with open(sp_path, 'rb') as f:
    data = f.read()

old = (
    b'    from app.services.paystack import PaystackClient\n'
    b'    from app.config import settings\n'
    b'    \n'
    b'    if not settings.paystack_secret_key:\n'
    b'        raise HTTPException(status_code=503, detail="Payment provider not configured")\n'
    b'    \n'
    b'    paystack = PaystackClient()\n'
)
new = (
    b'    from app.services.paystack import get_client as get_paystack_client\n'
    b'    from app.config import settings\n'
    b'    \n'
    b'    if not settings.paystack_secret_key:\n'
    b'        raise HTTPException(status_code=503, detail="Payment provider not configured")\n'
    b'    \n'
    b'    paystack = get_paystack_client()\n'
)
assert old in data, 'sponsor old block not found'
assert b'paystack = PaystackClient()\n' not in data.replace(old, b'', 1), 'sponsor has more than one PaystackClient()'
data = data.replace(old, new, 1)
with open(sp_path, 'wb') as f:
    f.write(data)
print('sponsor.py: fixed PaystackClient() -> get_paystack_client()')

# 2. fraud_detection.py
fd_path = r'C:\Users\kenik\OneDrive\Desktop\pagepay\backend\app\services\fraud_detection.py'
with open(fd_path, 'rb') as f:
    data = f.read()

# Drop User from the import (if still there) — already removed in some attempts
imp_old = (
    b'from app.models import (\n'
    b'    FraudFlag, TaskSubmission, User, ReadingSession, \n'
    b'    Referral\n'
    b')'
)
imp_new = (
    b'from app.models import (\n'
    b'    FraudFlag, TaskSubmission, ReadingSession, \n'
    b'    Referral\n'
    b')'
)
if imp_old in data:
    data = data.replace(imp_old, imp_new, 1)
    print('fraud_detection.py: removed unused User import')
else:
    print('fraud_detection.py: User import already gone (or already updated)')

# Fix check_duplicate_accounts to query TaskSubmission
old_dup = (
    b'        # Find other users with same device fingerprint\n'
    b'        duplicate_users = []\n'
    b'        \n'
    b'        if device_fingerprint:\n'
    b'            stmt = select(User).where(\n'
    b'                and_(\n'
    b'                    User.device_fingerprint == device_fingerprint,\n'
    b'                    User.id != user_id\n'
    b'                )\n'
    b'            ).limit(10)\n'
    b'            \n'
    b'            result = await self.db.execute(stmt)\n'
    b'            users = result.scalars().all()\n'
    b'            duplicate_users.extend([u.id for u in users])\n'
    b'        \n'
    b'        if len(duplicate_users) >= 2:  # 3+ accounts from same device\n'
    b'            flag = FraudFlag(\n'
    b'                user_id=user_id,\n'
    b'                session_id=None,\n'
    b'                flag_type="duplicate_account",\n'
    b'                severity="high" if len(duplicate_users) >= 5 else "medium",\n'
    b'                details=f"Device fingerprint shared with {len(duplicate_users)} other accounts: {duplicate_users[:5]}",\n'
    b'                status="pending"\n'
    b'            )'
)
new_dup = (
    b'        # Count other submissions on the same device or IP.\n'
    b'        # We use TaskSubmission (not User) because that is where\n'
    b'        # device_fingerprint and ip_address are actually persisted.\n'
    b'        duplicate_user_ids: set[int] = set()\n'
    b'        \n'
    b'        if device_fingerprint:\n'
    b'            stmt = select(TaskSubmission.worker_id).where(\n'
    b'                and_(\n'
    b'                    TaskSubmission.device_fingerprint == device_fingerprint,\n'
    b'                    TaskSubmission.worker_id != user_id,\n'
    b'                )\n'
    b'            ).limit(50)\n'
    b'            result = await self.db.execute(stmt)\n'
    b'            duplicate_user_ids.update(row[0] for row in result.all() if row[0] is not None)\n'
    b'        \n'
    b'        if ip_address:\n'
    b'            stmt = select(TaskSubmission.worker_id).where(\n'
    b'                and_(\n'
    b'                    TaskSubmission.ip_address == ip_address,\n'
    b'                    TaskSubmission.worker_id != user_id,\n'
    b'                )\n'
    b'            ).limit(50)\n'
    b'            result = await self.db.execute(stmt)\n'
    b'            duplicate_user_ids.update(row[0] for row in result.all() if row[0] is not None)\n'
    b'        \n'
    b'        duplicate_count = len(duplicate_user_ids)\n'
    b'        if duplicate_count >= 2:  # 3+ accounts (this user + 2 others) on same device\n'
    b'            flag = FraudFlag(\n'
    b'                user_id=user_id,\n'
    b'                session_id=None,\n'
    b'                flag_type="duplicate_account",\n'
    b'                severity="high" if duplicate_count >= 5 else "medium",\n'
    b'                details=f"Device/IP shared with {duplicate_count} other accounts: {sorted(duplicate_user_ids)[:5]}",\n'
    b'                status="pending"\n'
    b'            )'
)
assert old_dup in data, 'fraud_detection old_dup block not found'
assert b'User.device_fingerprint' in data, 'expected User.device_fingerprint to still be present'
data = data.replace(old_dup, new_dup, 1)
with open(fd_path, 'wb') as f:
    f.write(data)
print('fraud_detection.py: rewrote check_duplicate_accounts to use TaskSubmission')

# Verify all three bugs are now fixed
for path, bad in [
    (sp_path, b'paystack = PaystackClient()\n'),
    (fd_path, b'User.device_fingerprint'),
    (fd_path, b'User.id != user_id'),
]:
    with open(path, 'rb') as f:
        d = f.read()
    import os
    name = os.path.basename(path)
    print(f'  {name} still has {bad!r}: {bad in d}')

for path, good in [
    (sp_path, b'get_paystack_client'),
    (fd_path, b'TaskSubmission.worker_id'),
]:
    with open(path, 'rb') as f:
        d = f.read()
    import os
    name = os.path.basename(path)
    print(f'  {name} has {good!r}: {good in d}')

# syntax
import ast
for path in [sp_path, fd_path]:
    with open(path, 'rb') as f:
        d = f.read()
    ast.parse(d)
    import os
    print(f'  {os.path.basename(path)} syntax OK')
