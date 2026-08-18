import { test, expect } from '@playwright/test';
import path from 'path';

test('debug full flow until generate', async ({ page }) => {
  page.on('response', (resp) => {
    if (resp.url().includes('/api/')) {
      console.log(`[API] ${resp.status()} ${resp.request().method()} ${resp.url().replace('http://127.0.0.1:8000','')}`);
    }
  });

  await page.goto('/');
  await page.locator('input[type="file"]').setInputFiles(path.join(__dirname, 'fixtures', 'sample-acceptance.docx'));
  await page.locator('button.btn-primary', { hasText: 'Upload DOCX' }).click();
  
  await expect(page.locator('.stepper .step-chip.active')).toContainText('Review', { timeout: 30000 });
  console.log('STEP 1 OK: reached Review');
  
  await page.locator('button.btn-primary', { hasText: 'Lanjut ke Variabel' }).click();
  await expect(page.locator('.stepper .step-chip.active')).toContainText('Variabel');
  console.log('STEP 2 OK: reached Variables');
  
  await page.locator('button.btn-primary', { hasText: 'Lanjut ke Generate' }).click();
  await expect(page.locator('.stepper .step-chip.active')).toContainText('Generate');
  console.log('STEP 3 OK: reached Generate');
  
  await page.locator('button.btn-primary', { hasText: 'Generate DOCX' }).click();
  
  await page.waitForTimeout(8000);
  const resultOk = await page.locator('.result-ok').count();
  const errorBox = await page.locator('.error').count();
  console.log('RESULT OK:', resultOk, '| ERROR BOX:', errorBox);
  if (errorBox > 0) console.log('ERROR TEXT:', await page.locator('.error').textContent());
});
