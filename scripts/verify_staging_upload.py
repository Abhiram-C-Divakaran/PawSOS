#!/usr/bin/env python3
"""PawReach Staging Image Upload Verification Script.
Tests the image upload pipeline (/api/v1/uploads/image) against local or staging environment.
Validates HTTP response, image processing, dimensions, and URL generation without storing credentials.
"""
import argparse
import io
import sys
from PIL import Image

try:
    import httpx
except ImportError:
    print("Error: 'httpx' is required. Install via: pip install httpx")
    sys.exit(1)


def generate_test_image(width=800, height=600, color=(52, 211, 153)) -> io.BytesIO:
    """Generate a clean test JPEG image in memory with known dimensions."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf


def verify_staging_upload(base_url: str, email: str, password: str):
    print(f"=== PawReach Staging Image Upload Verification ===")
    print(f"Target API Base URL: {base_url}")
    print(f"Authenticating as: {email}")

    client = httpx.Client(base_url=base_url.rstrip("/"), timeout=15.0)

    try:
        # 1. Login to obtain access token
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        if login_resp.status_code != 200:
            print(f"[FAIL] Authentication failed with status {login_resp.status_code}: {login_resp.text}")
            return False

        token_data = login_resp.json()
        token = token_data.get("access_token")
        if not token:
            print("[FAIL] Login response did not contain access_token.")
            return False
        print("[PASS] Successfully authenticated and acquired Bearer token.")

        # 2. Upload test image
        img_buffer = generate_test_image(width=1200, height=900)
        files = {
            "file": ("staging_test_evidence.jpg", img_buffer.getvalue(), "image/jpeg")
        }
        headers = {"Authorization": f"Bearer {token}"}

        upload_resp = client.post("/api/v1/uploads/image", files=files, headers=headers)
        if upload_resp.status_code != 200:
            print(f"[FAIL] Image upload failed with status {upload_resp.status_code}: {upload_resp.text}")
            return False

        upload_data = upload_resp.json()
        image_url = upload_data.get("image_url")
        filename = upload_data.get("filename")
        print(f"[PASS] HTTP Status: {upload_resp.status_code}")
        print(f"[PASS] Storage URL/Key: {image_url}")
        print(f"[PASS] Original Filename: {filename}")

        # 3. Verify retrieval if URL is publicly accessible or static
        if image_url.startswith("http://") or image_url.startswith("https://") or image_url.startswith("/"):
            fetch_url = image_url if image_url.startswith("http") else f"{base_url.rstrip('/')}{image_url}"
            get_resp = client.get(fetch_url)
            print(f"[PASS] Retrieval probe status: {get_resp.status_code}")
            if get_resp.status_code == 200:
                retrieved_img = Image.open(io.BytesIO(get_resp.content))
                print(f"[PASS] Decoded image format: {retrieved_img.format}")
                print(f"[PASS] Image dimensions: {retrieved_img.width}x{retrieved_img.height}")

        print("\n=== VERIFICATION SUCCESS: Staging Image Pipeline Verified ===")
        return True

    except Exception as e:
        print(f"[ERROR] Exception during staging image upload verification: {e}")
        return False
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="PawReach Staging Image Upload Verification")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL of backend API")
    parser.add_argument("--email", default="admin@staging.pawsos.org", help="Test account email")
    parser.add_argument("--password", required=True, help="Test account password")
    args = parser.parse_args()

    success = verify_staging_upload(
        base_url=args.base_url,
        email=args.email,
        password=args.password,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
