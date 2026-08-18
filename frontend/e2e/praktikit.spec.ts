import { test, expect } from '@playwright/test';
import path from 'path';

/**
 * E2E test for PraktiKit full flow:
 * Upload → Analyze → Review → Variables → Generate → Download
 * 
 * Prerequisites:
 * - Backend API running at http://127.0.0.1:8000
 * - Frontend dev server at http://127.0.0.1:3000 (started by webServer in config)
 */

test.describe('PraktiKit Full Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('PraktiKit');
  });

  test('should complete full flow: upload → analyze → generate → download', async ({ page }) => {
    // Step 1: Upload
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Upload');
    
    const fileInput = page.locator('input[type="file"]');
    const sampleFile = path.join(__dirname, 'fixtures', 'sample-acceptance.docx');
    
    await fileInput.setInputFiles(sampleFile);
    await expect(page.locator('.dz-title')).toContainText('sample-acceptance.docx');
    
    // Click upload button
    const uploadButton = page.locator('button.btn-primary', { hasText: 'Upload DOCX' });
    await expect(uploadButton).toBeEnabled();
    await uploadButton.click();
    
    // Step 2: Analyzing (loading state)
    await expect(page.locator('.analyzing')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.analyzing')).toContainText('Menganalisis dokumen');
    
    // Wait for analysis to complete and move to review step
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Review', { timeout: 30000 });
    
    // Step 3: Review - verify analysis results
    await expect(page.locator('h2').first()).toContainText('sample-acceptance.docx');
    
    // Check stats are displayed
    await expect(page.locator('.stats')).toBeVisible();
    await expect(page.locator('.stat')).toHaveCount(6); // BAB, Subbagian, Tabel, Gambar, Variable, Paragraf
    
    // Check structure tree is visible
    await expect(page.locator('.tree')).toBeVisible();
    await expect(page.locator('.node')).toHaveCount(12, { timeout: 5000 }); // Cover + headings
    
    // Click next to variables
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Variabel' }).click();
    
    // Step 4: Variables
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Variabel');
    await expect(page.locator('h2')).toContainText('Variabel terdeteksi');
    
    // Verify variables detected (Nama, NIM)
    await expect(page.locator('.row')).toHaveCount(2, { timeout: 5000 }); // 2 variables
    await expect(page.locator('strong', { hasText: 'Nama' })).toBeVisible();
    await expect(page.locator('strong', { hasText: 'NIM' })).toBeVisible();
    
    // Check placeholders
    await expect(page.locator('.badge-muted', { hasText: '{{NAMA}}' })).toBeVisible();
    await expect(page.locator('.badge-muted', { hasText: '{{NIM}}' })).toBeVisible();
    
    // Click next to generate
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Generate' }).click();
    
    // Step 5: Generate
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Generate');
    await expect(page.locator('h2')).toContainText('Mode output');
    
    // Verify mode selector
    await expect(page.locator('.seg button', { hasText: 'Template bersih' })).toHaveClass(/on/);
    
    // Click generate
    const generateButton = page.locator('button.btn-primary', { hasText: 'Generate DOCX' });
    await generateButton.click();
    
    // Wait for generation to complete
    await expect(page.locator('.result-ok')).toContainText('Template berhasil dibuat', { timeout: 30000 });
    
    // Verify summary stats
    await expect(page.locator('.check')).toBeVisible();
    await expect(page.locator('.check li').first()).toContainText('variable diganti');
    await expect(page.locator('.check li').nth(1)).toContainText('paragraf lama dibersihkan');
    
    // Verify download link exists
    const downloadLink = page.locator('a.btn-primary', { hasText: 'Download DOCX' });
    await expect(downloadLink).toBeVisible();
    await expect(downloadLink).toHaveAttribute('href', /\/api\/documents\/[a-f0-9]+\/download/);
  });

  test('should allow personalized mode with variable values', async ({ page }) => {
    // Upload
    const fileInput = page.locator('input[type="file"]');
    const sampleFile = path.join(__dirname, 'fixtures', 'sample-custom-heading.docx');
    await fileInput.setInputFiles(sampleFile);
    await page.locator('button.btn-primary', { hasText: 'Upload DOCX' }).click();
    
    // Wait for review
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Review', { timeout: 30000 });
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Variabel' }).click();
    
    // Variables step - fill values
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Variabel');
    
    // Enable first variable (Nama)
    const namaRow = page.locator('.row', { has: page.locator('strong', { hasText: 'Nama' }) });
    await namaRow.locator('button', { hasText: 'Lewati' }).click();
    await expect(namaRow.locator('button', { hasText: 'Isi' })).toBeVisible();
    
    // Fill value
    const namaInput = namaRow.locator('input');
    await expect(namaInput).toBeEnabled();
    await namaInput.fill('Jiyad Ahmad');
    
    // Enable NIM
    const nimRow = page.locator('.row', { has: page.locator('strong', { hasText: 'NIM' }) });
    await nimRow.locator('button', { hasText: 'Lewati' }).click();
    const nimInput = nimRow.locator('input');
    await nimInput.fill('24100001');
    
    // Go to generate
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Generate' }).click();
    
    // Select personalized mode
    await page.locator('.seg button', { hasText: 'Laporan baru' }).click();
    await expect(page.locator('.seg button', { hasText: 'Laporan baru' })).toHaveClass(/on/);
    
    // Generate
    await page.locator('button.btn-primary', { hasText: 'Generate DOCX' }).click();
    await expect(page.locator('.result-ok')).toContainText('Template berhasil dibuat', { timeout: 30000 });
    
    // Verify download available
    await expect(page.locator('a.btn-primary', { hasText: 'Download DOCX' })).toBeVisible();
  });

  test('should handle table identity document', async ({ page }) => {
    // Upload table fixture
    const fileInput = page.locator('input[type="file"]');
    const sampleFile = path.join(__dirname, 'fixtures', 'sample-table.docx');
    await fileInput.setInputFiles(sampleFile);
    await page.locator('button.btn-primary', { hasText: 'Upload DOCX' }).click();
    
    // Wait for review
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Review', { timeout: 30000 });
    
    // Verify table detected
    const stats = page.locator('.stats');
    const tablesCount = stats.locator('.stat', { has: page.locator('.lbl', { hasText: 'Tabel' }) });
    await expect(tablesCount.locator('.num')).toContainText('2'); // Identity + data table
    
    // Go through flow
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Variabel' }).click();
    
    // Verify table variables detected
    await expect(page.locator('.row')).toHaveCount(2, { timeout: 5000 }); // Nama, NIM from table
    await expect(page.locator('.muted small', { hasText: 'table' })).toHaveCount(2);
    
    // Complete flow
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Generate' }).click();
    await page.locator('button.btn-primary', { hasText: 'Generate DOCX' }).click();
    await expect(page.locator('.result-ok')).toContainText('Template berhasil dibuat', { timeout: 30000 });
  });

  test('should show error for invalid file', async ({ page }) => {
    // Try to upload without selecting file
    const uploadButton = page.locator('button.btn-primary', { hasText: 'Upload DOCX' });
    await expect(uploadButton).toBeDisabled();
  });
});

test.describe('PraktiKit UI Navigation', () => {
  test('should allow back navigation', async ({ page }) => {
    await page.goto('/');
    
    // Upload and analyze
    const fileInput = page.locator('input[type="file"]');
    const sampleFile = path.join(__dirname, 'fixtures', 'sample-acceptance.docx');
    await fileInput.setInputFiles(sampleFile);
    await page.locator('button.btn-primary', { hasText: 'Upload DOCX' }).click();
    
    // Wait for review
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Review', { timeout: 30000 });
    
    // Go to variables
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Variabel' }).click();
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Variabel');
    
    // Back to review
    await page.locator('button.btn', { hasText: '← Review' }).click();
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Review');
    
    // Forward again
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Variabel' }).click();
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Variabel');
    
    // Go to generate
    await page.locator('button.btn-primary', { hasText: 'Lanjut ke Generate' }).click();
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Generate');
    
    // Back to variables
    await page.locator('button.btn', { hasText: '← Variabel' }).click();
    await expect(page.locator('.stepper .step-chip.active')).toContainText('Variabel');
  });
});
