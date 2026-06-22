import pytest
from unittest.mock import patch, AsyncMock
from app.db.mongo import get_db

pytestmark = pytest.mark.asyncio

async def test_register_success(client):
    response = await client.post("/auth/register", json={
        "email": "testuser@example.com",
        "username": "testuser",
        "password": "strongpassword123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == "testuser@example.com"
    assert data["user"]["username"] == "testuser"
    assert "access_token" in data
    assert "refresh_token" in data
    
    # Verify in DB
    db = get_db()
    db_user = await db["users"].find_one({"email": "testuser@example.com"})
    assert db_user is not None
    assert db_user["username"] == "testuser"
    assert db_user["is_admin"] is False
    assert "password_hash" in db_user
    
    # Ensure no passwords or secrets leaked in JSON response
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]
    assert "otp_hash" not in data["user"]

async def test_register_duplicate_email(client):
    # Register first user
    resp1 = await client.post("/auth/register", json={
        "email": "duplicate@example.com",
        "username": "firstuser",
        "password": "password123"
    })
    assert resp1.status_code == 200

    # Try duplicate email (case-insensitive)
    resp2 = await client.post("/auth/register", json={
        "email": "DUPLICATE@example.com",
        "username": "seconduser",
        "password": "password123"
    })
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "Email already registered"

async def test_register_duplicate_username(client):
    # Register first user
    resp1 = await client.post("/auth/register", json={
        "email": "first@example.com",
        "username": "duplicate_user",
        "password": "password123"
    })
    assert resp1.status_code == 200

    # Try duplicate username (case-insensitive)
    resp2 = await client.post("/auth/register", json={
        "email": "second@example.com",
        "username": "DUPLICATE_USER",
        "password": "password123"
    })
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "Username already taken"

async def test_register_validation(client):
    # Password too short
    resp = await client.post("/auth/register", json={
        "email": "valid@example.com",
        "username": "validuser",
        "password": "123"
    })
    assert resp.status_code == 400
    assert "Password must be at least 6 characters" in resp.json()["detail"]

    # Username too short
    resp = await client.post("/auth/register", json={
        "email": "valid@example.com",
        "username": "va",
        "password": "password123"
    })
    assert resp.status_code == 400
    assert "Username must be at least 3 characters" in resp.json()["detail"]

    # Username invalid characters
    resp = await client.post("/auth/register", json={
        "email": "valid@example.com",
        "username": "user-invalid!",
        "password": "password123"
    })
    assert resp.status_code == 400
    assert "Username can only contain letters, numbers, underscores and dots" in resp.json()["detail"]

async def test_login_success(client):
    # Register
    await client.post("/auth/register", json={
        "email": "loginuser@example.com",
        "username": "loginuser",
        "password": "password123"
    })

    # Login via email
    resp_email = await client.post("/auth/login", json={
        "identifier": "LOGINUSER@example.com",
        "password": "password123"
    })
    assert resp_email.status_code == 200
    assert "access_token" in resp_email.json()
    assert "refresh_token" in resp_email.json()

    # Login via username
    resp_user = await client.post("/auth/login", json={
        "identifier": "loginuser",
        "password": "password123"
    })
    assert resp_user.status_code == 200

async def test_login_failure(client):
    # Register
    await client.post("/auth/register", json={
        "email": "fail@example.com",
        "username": "failuser",
        "password": "password123"
    })

    # Wrong password
    resp = await client.post("/auth/login", json={
        "identifier": "failuser",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401
    assert "Invalid email/username or password" in resp.json()["detail"]

    # Non-existent user
    resp = await client.post("/auth/login", json={
        "identifier": "nonexistent",
        "password": "password123"
    })
    assert resp.status_code == 401

async def test_refresh_token_rotation_and_revocation(client):
    # Register
    register_resp = await client.post("/auth/register", json={
        "email": "refresh@example.com",
        "username": "refreshuser",
        "password": "password123"
    })
    refresh_token = register_resp.json()["refresh_token"]

    # Refresh access token
    refresh_resp = await client.post("/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    new_refresh_token = new_data["refresh_token"]

    # Try refreshing again with the old (rotated) token - should fail
    fail_resp = await client.post("/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert fail_resp.status_code == 401

    # Revoke via logout
    logout_resp = await client.post("/auth/logout", json={
        "refresh_token": new_refresh_token
    })
    assert logout_resp.status_code == 200

    # Try refreshing again with revoked new token
    fail_resp2 = await client.post("/auth/refresh", json={
        "refresh_token": new_refresh_token
    })
    assert fail_resp2.status_code == 401

async def test_logout_all(client):
    # Register and login twice to simulate two devices
    reg_resp = await client.post("/auth/register", json={
        "email": "logoutall@example.com",
        "username": "logoutall",
        "password": "password123"
    })
    token1 = reg_resp.json()["refresh_token"]
    access_token = reg_resp.json()["access_token"]

    login_resp = await client.post("/auth/login", json={
        "identifier": "logoutall",
        "password": "password123"
    })
    token2 = login_resp.json()["refresh_token"]

    # Call logout-all using auth headers
    headers = {"Authorization": f"Bearer {access_token}"}
    logout_all_resp = await client.post("/auth/logout-all", headers=headers)
    assert logout_all_resp.status_code == 200

    # Both refresh tokens should now be invalid
    for tok in [token1, token2]:
        resp = await client.post("/auth/refresh", json={"refresh_token": tok})
        assert resp.status_code == 401

async def test_forgot_and_reset_password_flow(client):
    # Register user
    await client.post("/auth/register", json={
        "email": "forgot@example.com",
        "username": "forgotuser",
        "password": "password123"
    })

    # Request password reset & capture sent email with OTP
    with patch("app.services.user_service.send_otp_email", new_callable=AsyncMock) as mock_send_email:
        forgot_resp = await client.post("/auth/forgot-password", json={
            "email": "forgot@example.com"
        })
        assert forgot_resp.status_code == 200
        assert "If this email is registered" in forgot_resp.json()["message"]
        
        # Verify email function was called
        mock_send_email.assert_called_once()
        captured_otp = mock_send_email.call_args[1]["otp"]

    # Verify OTP
    verify_resp = await client.post("/auth/verify-otp", json={
        "email": "forgot@example.com",
        "otp": captured_otp
    })
    assert verify_resp.status_code == 200

    # Reset password with mismatching confirm password
    reset_fail = await client.post("/auth/reset-password", json={
        "email": "forgot@example.com",
        "otp": captured_otp,
        "new_password": "newpassword123",
        "confirm_password": "mismatchpassword"
    })
    assert reset_fail.status_code == 400

    # Reset password successfully
    reset_success = await client.post("/auth/reset-password", json={
        "email": "forgot@example.com",
        "otp": captured_otp,
        "new_password": "newpassword123",
        "confirm_password": "newpassword123"
    })
    assert reset_success.status_code == 200

    # Try login with old password - should fail
    login_old = await client.post("/auth/login", json={
        "identifier": "forgotuser",
        "password": "password123"
    })
    assert login_old.status_code == 401

    # Try login with new password - should succeed
    login_new = await client.post("/auth/login", json={
        "identifier": "forgotuser",
        "password": "newpassword123"
    })
    assert login_new.status_code == 200

async def test_no_data_leakage(client):
    # Verify profile endpoint and response schema contains no hash
    reg_resp = await client.post("/auth/register", json={
        "email": "leaktest@example.com",
        "username": "leaktest",
        "password": "password123"
    })
    access_token = reg_resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = await client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert "password_hash" not in me_data
    assert "otp_hash" not in me_data
    assert "password" not in me_data

async def test_mongo_injection_resistance(client):
    # Try passing a dictionary for a string field, which would trigger a Pydantic validation error (422)
    resp = await client.post("/auth/login", json={
        "identifier": {"$ne": ""},
        "password": "password123"
    })
    assert resp.status_code == 422
