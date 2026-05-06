# Project Theia

Inventory scanning powered by computer vision. Point your iPhone at a freezer full of boxes and get an instant tally by product.

## How it works

1. User photographs boxes in the freezer using the iOS app
2. Image is sent to the Python backend
3. AWS Rekognition reads text labels on each box
4. Results are tallied by product and displayed in-app

## Structure

```
project-theia/
├── mobile/        # React Native (Expo) iOS app
├── backend/       # Python FastAPI backend
└── infrastructure/ # AWS setup notes
```

## Prerequisites

- AWS account with Rekognition access
- Python 3.11+
- Node.js 18+
- Expo Go app on your iPhone (for development)

## Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env       # fill in your AWS credentials
uvicorn main:app --reload
```

## Mobile setup

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with Expo Go on your iPhone.

## AWS setup

See [infrastructure/README.md](infrastructure/README.md) for the required IAM policy.
