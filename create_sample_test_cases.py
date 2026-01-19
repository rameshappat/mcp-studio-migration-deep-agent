#!/usr/bin/env python
"""Create sample test cases manually for the existing test plan."""

import asyncio
import os
import json
from dotenv import load_dotenv
load_dotenv()

from src.mcp_client.ado_client import AzureDevOpsMCPClient

# Sample work items (you can customize these based on your project)
SAMPLE_WORK_ITEMS = [
    {
        "title": "User Registration with Email Verification",
        "test_steps": """1. Navigate to /register page and verify form displays|Registration form shows with email, password, confirm password fields and submit button
2. Enter valid email 'user@test.com' and strong password 'Test123!@#'|Fields accept input, password strength indicator shows 'Strong'
3. Enter matching password in confirm field and click Submit|Loading indicator appears, submit button disabled during processing
4. Check email inbox for verification message|Verification email arrives within 30 seconds with subject 'Verify Your Account'
5. Click verification link in email|Browser redirects to /verified page with success message 'Email verified successfully'
6. Attempt to login with verified credentials|Login succeeds and redirects to dashboard"""
    },
    {
        "title": "User Login with JWT Authentication",
        "test_steps": """1. Navigate to /login page|Login form displays with email and password fields
2. Enter valid registered email and password|Fields accept input without errors
3. Click Login button|Loading indicator appears, API request sent to /api/auth/login
4. Verify JWT token is returned and stored|Token appears in localStorage with key 'authToken', expires in 24 hours
5. Check Authorization header on subsequent requests|All API requests include 'Authorization: Bearer [token]' header
6. Verify user is redirected to dashboard|Dashboard page loads showing user's name and profile picture"""
    },
    {
        "title": "Create New User Profile with Multi-Factor Authentication",
        "test_steps": """1. Login and navigate to Profile Settings page|Profile settings form displays with MFA setup option
2. Click 'Enable MFA' button|QR code displays with authenticator app instructions
3. Scan QR code with authenticator app (Google Authenticator)|App generates 6-digit verification code
4. Enter verification code and click Verify|Success message: 'MFA enabled successfully', backup codes displayed
5. Save backup codes and logout|System logs user out and redirects to login page
6. Login again and verify MFA prompt appears|After password entry, system prompts for 6-digit MFA code"""
    },
    {
        "title": "RESTful API CRUD Operations for User Management",
        "test_steps": """1. Send POST request to /api/users with new user data|API returns 201 Created with user object including generated ID
2. Send GET request to /api/users/:id|API returns 200 OK with complete user object matching created user
3. Send PUT request to /api/users/:id with updated fields|API returns 200 OK with updated user data, changes persist in database
4. Send GET request to /api/users to list all users|API returns 200 OK with array of users, pagination headers included
5. Send DELETE request to /api/users/:id|API returns 204 No Content, user marked as deleted (soft delete)
6. Verify deleted user no longer appears in GET /api/users list|API response excludes deleted user from results"""
    },
    {
        "title": "Database Schema and Data Validation",
        "test_steps": """1. Connect to database and verify users table exists|Table 'users' present with expected columns: id, email, password_hash, created_at, updated_at
2. Check foreign key constraints on related tables|user_profiles table has valid FK to users.id, cascade delete configured
3. Insert test user with all required fields|Record inserted successfully, timestamps auto-populated
4. Attempt to insert duplicate email address|Unique constraint violation raised, error message: 'Email already exists'
5. Verify password is hashed before storage|Password column contains bcrypt hash starting with '$2b$', not plaintext
6. Check database indexes for performance|Indexes exist on users.email (unique) and users.created_at for query optimization"""
    }
]

async def create_test_cases():
    """Create test cases for existing test plan 369."""
    
    # Initialize ADO client
    client = AzureDevOpsMCPClient(
        organization='appatr',
        project='testingmcp',
        auth_type='envvar'
    )
    
    await client.connect()
    
    print("=" * 60)
    print("CREATING TEST CASES FOR TEST PLAN 369")
    print("=" * 60)
    
    test_plan_id = 369
    test_suite_id = 370
    created_cases = []
    
    for idx, work_item in enumerate(SAMPLE_WORK_ITEMS, 1):
        print(f"\n{idx}. Creating test case: {work_item['title']}")
        
        try:
            # Create test case
            result = await client.call_tool('testplan_create_test_case', {
                'project': 'testingmcp',
                'title': f"Test: {work_item['title']}",
                'steps': work_item['test_steps']
            })
            
            print(f"   Result type: {type(result)}")
            
            # Parse the result
            if isinstance(result, dict):
                test_case_id = result.get('id')
                if test_case_id:
                    print(f"   ✅ Test case created: ID {test_case_id}")
                    created_cases.append(test_case_id)
                    
                    # Add to test suite
                    print(f"   Adding to test suite {test_suite_id}...")
                    add_result = await client.call_tool('testplan_add_test_cases_to_suite', {
                        'project': 'testingmcp',
                        'test_plan_id': test_plan_id,
                        'test_suite_id': test_suite_id,
                        'test_case_ids': [test_case_id]
                    })
                    print(f"   ✅ Added to suite")
                else:
                    print(f"   ⚠️  No ID in result: {result}")
            else:
                print(f"   ⚠️  Unexpected result: {result}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    await client.close()
    
    print("\n" + "=" * 60)
    print(f"✅ CREATED {len(created_cases)} TEST CASES")
    print("=" * 60)
    print(f"Test Plan ID: {test_plan_id}")
    print(f"Test Suite ID: {test_suite_id}")
    print(f"Test Case IDs: {created_cases}")

if __name__ == "__main__":
    asyncio.run(create_test_cases())
