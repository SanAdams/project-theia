# Project Theia

Inventory scanning powered by computer vision. Point your Android phone at a freezer full of boxes and get an instant tally by product.

## How it works

1. User photographs boxes in the freezer using the Android app
2. Image is sent to the Python backend
3. AWS Rekognition reads text labels on each box
4. Labels are fuzzy-matched against a known product list to normalize OCR variations
5. Results are tallied by product and displayed in-app

## Structure

```
project-theia/
├── mobile/         # React Native (Expo) app — Android-first, iOS-ready
├── backend/        # Python FastAPI backend
└── infrastructure/ # AWS setup notes
```

## Prerequisites

- AWS account with Rekognition access
- Python 3.11+
- Node.js 18+
- Expo Go app on your Android device (for development)

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

Scan the QR code with Expo Go on your Android device, or press `a` to open in an Android emulator.

## Product normalization

The backend fuzzy-matches detected labels against a known product list (`backend/products.json`) to handle OCR typos and casing variations. Populate that file with your canonical product names before scanning.

## AWS setup

See [infrastructure/README.md](infrastructure/README.md) for the required IAM policy.
