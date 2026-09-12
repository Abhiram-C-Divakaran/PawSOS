import { Page, APIRequestContext } from '@playwright/test';

export const API_BASE_URL = process.env.API_BASE_URL || 'http://127.0.0.1:8000/api/v1';
export const DEFAULT_E2E_PASSWORD = 'E2ETestPassword123!';

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function loginViaApi(
  request: APIRequestContext,
  email: string,
  password: string = DEFAULT_E2E_PASSWORD
): Promise<LoginResponse> {
  const response = await request.post(`${API_BASE_URL}/auth/login`, {
    form: {
      username: email,
      password: password,
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed API login for ${email}: ${response.status()} ${await response.text()}`);
  }

  return await response.json();
}

export async function authenticatePage(
  page: Page,
  email: string,
  password: string = DEFAULT_E2E_PASSWORD
): Promise<LoginResponse> {
  const tokenData = await loginViaApi(page.request, email, password);

  // Set tokens in browser context before navigating
  await page.addInitScript(
    ({ access_token, refresh_token }) => {
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
    },
    { access_token: tokenData.access_token, refresh_token: tokenData.refresh_token }
  );

  return tokenData;
}
