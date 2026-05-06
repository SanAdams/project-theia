# Infrastructure

## Required IAM policy

Create an IAM user in your AWS account and attach this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["rekognition:DetectText"],
      "Resource": "*"
    }
  ]
}
```

Then generate an access key for that user and add the credentials to `backend/.env`.

## Regions

AWS Rekognition is available in most regions. `us-east-1` is the default.
Pick the region closest to where the backend will be deployed.
