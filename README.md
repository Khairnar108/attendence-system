# Register  —  Attendance Control System

A full attendance system built on Flask: admin/employee roles, a punch-clock
check-in flow, a daily attendance ledger with CSV export, and an employee
roster with  auto-generated logins. Deployed automatically on every push to
GitHub via GitHub Actions → S3 → AWS CodeDeploy → EC2.

## What's actually in here you think

- **Authentication** — Flask-Login, hashed passwords, two roles (`admin`, `employee`)
- **Database** — SQLAlchemy models (`Employee`, `User`, `Attendance`), SQLite by default, swap to Postgres/MySQL by setting `DATABASE_URL`
- **Admin side** — dashboard with live counts, employee roster (add/edit/deactivate), daily ledger (mark status, edit any employee's day), CSV export per day
- **Employee side** — punch clock (in/out with live time), personal history with month filter
- **Production server** — Gunicorn behind systemd, not the Flask dev server

---

## 1. Run it locally first (recommended before touching AWS)

```bash
cd attendance-control-system
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

python seed.py                  # creates the admin login + 3 sample employees
python run.py
```

Open `http://localhost:3000`. Sign in as:

- **Admin** — ID `admin` / passcode `admin123`
- **Sample employee** — ID `EMP-001` / passcode `EMP-001123`

`seed.py` prints every login it creates — use those, or add real employees
from the Roster once you're in as admin (a login is generated automatically
for each new employee).

**Change the admin passcode and the `SECRET_KEY` before this goes anywhere
real.** There's no "change password" screen yet — the fastest way for now is
opening a Python shell:

```python
from app import create_app, db
from app.models import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    u.set_password("your-new-passcode")
    db.session.commit()
```

---

## 2. Push this project to GitHub

```bash
git init
git add .
git commit -m "Initial commit - attendance control system"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

---

## 3. Create an S3 bucket (holds the zipped app before CodeDeploy picks it up)

1. AWS Console → **S3** → **Create bucket**
2. Name: `attendance-app-deploy-<yourname>-<random-number>` (must be globally unique)
3. Region: pick one and remember it, e.g. `ap-south-1` (Mumbai)
4. Leave defaults → **Create bucket**

---

## 4. Launch the EC2 instance

1. EC2 → **Launch instance**
2. Name: `attendance-app-server`
3. AMI: **Amazon Linux 2023**
4. Type: `t2.micro` (free tier)
5. Key pair: create new, download the `.pem`, keep it safe
6. Security group inbound rules:
   - SSH (22) — Source: My IP
   - Custom TCP (3000) — Source: Anywhere (0.0.0.0/0)
7. Launch, note the **Public IPv4 address**

---

## 5. Install Python and the CodeDeploy agent on the instance

```bash
ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP>
```

```bash
sudo yum update -y
sudo yum install -y python3 python3-pip python3-devel gcc ruby wget

# CodeDeploy agent
cd /home/ec2-user
wget https://aws-codedeploy-ap-south-1.s3.ap-south-1.amazonaws.com/latest/install
# Replace "ap-south-1" with YOUR region if different — full list:
# https://docs.aws.amazon.com/codedeploy/latest/userguide/resource-kit.html#resource-kit-bucket-names
chmod +x ./install
sudo ./install auto
sudo service codedeploy-agent status   # should say "is running"

mkdir -p /home/ec2-user/attendance-app
exit
```

---

## 6. IAM role for the EC2 instance (lets the CodeDeploy agent read from S3)

1. IAM → **Roles** → **Create role** → Trusted entity: **EC2**
2. Attach policy: `AmazonEC2RoleforAWSCodeDeploy`
3. Name: `EC2-CodeDeploy-Role`
4. EC2 → select instance → **Actions → Security → Modify IAM role** → attach it

---

## 7. IAM role for the CodeDeploy service itself

1. IAM → **Roles** → **Create role** → Trusted entity: **CodeDeploy** → use case **CodeDeploy**
2. This auto-attaches `AWSCodeDeployRole` — confirm, create
3. Name: `CodeDeployServiceRole`

---

## 8. Tag the instance

EC2 → instance → **Tags** → confirm `Name` = `attendance-app-server` (CodeDeploy targets instances by tag, not ID).

---

## 9. Create the CodeDeploy application + deployment group

1. CodeDeploy → **Applications** → **Create application**
   - Name: `attendance-app`, Compute platform: **EC2/On-premises**
2. Inside it → **Create deployment group**
   - Name: `attendance-app-group`
   - Service role: `CodeDeployServiceRole`
   - Deployment type: **In-place**
   - Environment: **Amazon EC2 instances**, tag `Name` = `attendance-app-server`
   - Deployment settings: `CodeDeployDefault.AllAtOnce`
   - Uncheck "Enable load balancing"
   - Create

---

## 10. IAM user for GitHub Actions (the "secret keys")

1. IAM → **Users** → **Create user** → name: `github-actions-deployer`
2. No console access — programmatic only
3. Attach policies: `AmazonS3FullAccess`, `AWSCodeDeployFullAccess`
   *(scope these down to your specific bucket/app for production)*
4. Create user → **Security credentials** → **Create access key** → use case **Third-party service**
5. Copy the Access key ID and Secret access key now — the secret won't be shown again

---

## 11. Add GitHub repository secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | from step 10 |
| `AWS_SECRET_ACCESS_KEY` | from step 10 |
| `AWS_REGION` | e.g. `ap-south-1` |
| `S3_BUCKET_NAME` | from step 3 |
| `CODEDEPLOY_APP_NAME` | `attendance-app` |
| `CODEDEPLOY_GROUP_NAME` | `attendance-app-group` |

---

## 12. Push and deploy

```bash
git add .
git commit -m "trigger deploy"
git push origin main
```

Watch it run: GitHub repo → **Actions** tab, and AWS Console → **CodeDeploy → Deployments**.

**After the first successful deploy**, SSH in once to seed the database
(the pipeline installs dependencies but deliberately doesn't auto-seed, so
you don't wipe real data on every push):

```bash
ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP>
cd attendance-app
source venv/bin/activate
python seed.py
deactivate
```

---

## 13. Verify

```
http://<EC2_PUBLIC_IP>:3000
```

Sign in with the admin credentials `seed.py` printed.

---

## Troubleshooting

- **App won't start** → `sudo systemctl status attendance-app` then `sudo journalctl -u attendance-app -n 50` on the EC2 instance.
- **CodeDeploy says "no instances found"** → tag in step 8 must exactly match the deployment group's tag filter.
- **GitHub Actions fails on `aws deploy create-deployment` with AccessDenied** → recheck IAM user policies (step 10) and that secret names (step 11) match exactly, case-sensitive.
- **CodeDeploy agent not responding** → `sudo service codedeploy-agent restart`, then `sudo tail -f /var/log/aws/codedeploy-agent/codedeploy-agent.log`.
- **Login works locally but not on EC2** → the database is per-environment; you need to run `python seed.py` on the EC2 instance too (step 12), not just locally.
- **Static files (CSS/fonts) not loading** → hard refresh; Flask serves `/static` automatically, no extra config needed.

---

## Where this is intentionally simple (and how to harden it)

- **SQLite by default** — fine for a single EC2 instance and moderate traffic. For multiple servers or real concurrency, set `DATABASE_URL` to a Postgres/MySQL RDS instance; the code doesn't change, only the connection string.
- **No password-reset UI yet** — admin resets passcodes by editing the `User` row directly (see section 1) or you can add a reset route.
- **IAM policies are broad** (`Full Access`) to keep first-time setup unblocked — scope them to the specific bucket/app before this holds real employee data.
- **No HTTPS** — this serves plain HTTP on port 3000. Put it behind Nginx + Let's Encrypt or an Application Load Balancer with an ACM certificate before using it outside a private network.
