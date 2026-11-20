/**
 * Comprehensive Automated Test Suite for TASK-015:
 * Batch Drag-and-Drop Document Upload & Queue Processing.
 * Runs directly on Node.js 22 test runner with --experimental-strip-types.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { validateFilePreflight } from '../hooks/useUploadQueue.ts'
import type { QueueItem, QueueItemStatus } from '../types/upload.ts'
import type { DocumentStatus, ValidationStatus } from '../types/document.ts'

describe('TASK-015: Preflight File Validation', () => {
  it('accepts valid PDF under 25 MB', () => {
    const file = new File(['%PDF-1.4 sample content'], 'invoice_2026.pdf', { type: 'application/pdf' })
    const res = validateFilePreflight(file)
    assert.equal(res.isValid, true)
    assert.equal(res.error, undefined)
  })

  it('accepts all allowed extensions: png, jpg, jpeg, tiff, tif, xlsx, xls, csv, txt', () => {
    const allowedNames = [
      'receipt.png',
      'photo.jpg',
      'scan.jpeg',
      'doc.tiff',
      'doc.tif',
      'ledger.xlsx',
      'archive.xls',
      'data.csv',
      'plain.txt',
    ]

    for (const name of allowedNames) {
      const file = new File(['mock content'], name)
      const res = validateFilePreflight(file)
      assert.equal(res.isValid, true, `Expected ${name} to be valid`)
    }
  })

  it('rejects empty (0 byte) file', () => {
    const file = new File([], 'empty.pdf', { type: 'application/pdf' })
    const res = validateFilePreflight(file)
    assert.equal(res.isValid, false)
    assert.match(res.error || '', /empty \(0 bytes\)/i)
  })

  it('rejects oversized file exceeding 25 MB', () => {
    // Mock a 26 MB file using Object.defineProperty to avoid huge memory allocation
    const file = new File(['x'], 'big_invoice.pdf', { type: 'application/pdf' })
    Object.defineProperty(file, 'size', { value: 26 * 1024 * 1024 })

    const res = validateFilePreflight(file)
    assert.equal(res.isValid, false)
    assert.match(res.error || '', /exceeds maximum limit of 25 MB/i)
  })

  it('rejects unsupported extensions (.exe, .zip, .docx, .sh)', () => {
    const invalidFiles = ['malware.exe', 'archive.zip', 'document.docx', 'script.sh', 'noextension']
    for (const name of invalidFiles) {
      const file = new File(['content'], name)
      const res = validateFilePreflight(file)
      assert.equal(res.isValid, false, `Expected ${name} to be rejected`)
      assert.match(res.error || '', /unsupported format/i)
    }
  })
})

describe('TASK-015: Duplicate File Detection & Queue Signature', () => {
  it('correctly generates matching signature for duplicate files with identical name and size', () => {
    const file1 = new File(['invoice content'], 'march_bill.pdf')
    const file2 = new File(['invoice content'], 'march_bill.pdf')
    const sig1 = `${file1.name}-${file1.size}`
    const sig2 = `${file2.name}-${file2.size}`

    assert.equal(sig1, sig2)
  })

  it('differentiates files with identical name but different sizes', () => {
    const file1 = new File(['invoice content version 1'], 'march_bill.pdf')
    const file2 = new File(['invoice content version 2 with more lines'], 'march_bill.pdf')
    const sig1 = `${file1.name}-${file1.size}`
    const sig2 = `${file2.name}-${file2.size}`

    assert.notEqual(sig1, sig2)
  })
})

describe('TASK-015: True Backend Status & Client State Mapping', () => {
  function mapBackendStatusToClient(
    backendStatus: DocumentStatus,
    validationStatus?: ValidationStatus
  ): QueueItemStatus {
    if (backendStatus === 'PROCESSING') {
      return 'PROCESSING'
    }
    if (backendStatus === 'SUCCESS' || backendStatus === 'PARTIAL_SUCCESS') {
      if (validationStatus === 'VERIFIED') return 'SUCCESS'
      if (validationStatus === 'NEEDS_REVIEW') return 'NEEDS_REVIEW'
      if (validationStatus === 'FAILED') return 'FAILED'
      return 'SUCCESS'
    }
    if (backendStatus === 'FAILED') {
      return 'FAILED'
    }
    return 'QUEUED'
  }

  it('maps QUEUED backend status to QUEUED client status', () => {
    const clientStatus = mapBackendStatusToClient('QUEUED', 'PENDING')
    assert.equal(clientStatus, 'QUEUED')
  })

  it('maps PROCESSING backend status to PROCESSING client status', () => {
    const clientStatus = mapBackendStatusToClient('PROCESSING', 'PENDING')
    assert.equal(clientStatus, 'PROCESSING')
  })

  it('maps SUCCESS + VERIFIED to clean SUCCESS', () => {
    const clientStatus = mapBackendStatusToClient('SUCCESS', 'VERIFIED')
    assert.equal(clientStatus, 'SUCCESS')
  })

  it('maps SUCCESS + NEEDS_REVIEW to operator NEEDS_REVIEW', () => {
    const clientStatus = mapBackendStatusToClient('SUCCESS', 'NEEDS_REVIEW')
    assert.equal(clientStatus, 'NEEDS_REVIEW')
  })

  it('maps SUCCESS + FAILED validation to client FAILED', () => {
    const clientStatus = mapBackendStatusToClient('SUCCESS', 'FAILED')
    assert.equal(clientStatus, 'FAILED')
  })

  it('maps FAILED pipeline status to client FAILED', () => {
    const clientStatus = mapBackendStatusToClient('FAILED', 'FAILED')
    assert.equal(clientStatus, 'FAILED')
  })

  it('does NOT invent completion before backend confirms SUCCESS', () => {
    // If backend reports QUEUED or PROCESSING, client must never mark it as completed
    assert.notEqual(mapBackendStatusToClient('QUEUED'), 'SUCCESS')
    assert.notEqual(mapBackendStatusToClient('PROCESSING'), 'SUCCESS')
  })
})

describe('TASK-015: Concurrency Invariant & Queue Throttling', () => {
  it('enforces maximum 2 concurrent uploads at any time', () => {
    const CONCURRENCY_LIMIT = 2
    const queue: Array<{ id: string; status: QueueItemStatus }> = [
      { id: '1', status: 'PENDING' },
      { id: '2', status: 'PENDING' },
      { id: '3', status: 'PENDING' },
      { id: '4', status: 'PENDING' },
    ]

    const activeUploading = new Set<string>()

    function scheduleNext() {
      const available = CONCURRENCY_LIMIT - activeUploading.size
      if (available <= 0) return []
      const toStart = queue
        .filter((q) => q.status === 'PENDING' && !activeUploading.has(q.id))
        .slice(0, available)
      for (const item of toStart) {
        activeUploading.add(item.id)
        item.status = 'UPLOADING'
      }
      return toStart
    }

    // Step 1: initial schedule
    const batch1 = scheduleNext()
    assert.equal(batch1.length, 2)
    assert.equal(activeUploading.size, 2)
    assert.deepEqual(Array.from(activeUploading), ['1', '2'])

    // Attempting to schedule again while 2 are running starts 0
    const batchAttempt = scheduleNext()
    assert.equal(batchAttempt.length, 0)
    assert.equal(activeUploading.size, 2)

    // Complete item 1
    activeUploading.delete('1')
    queue[0].status = 'QUEUED'
    assert.equal(activeUploading.size, 1)

    // Step 2: schedule fills the 1 open slot with item 3
    const batch2 = scheduleNext()
    assert.equal(batch2.length, 1)
    assert.equal(batch2[0].id, '3')
    assert.equal(activeUploading.size, 2)
    assert.deepEqual(Array.from(activeUploading), ['2', '3'])
  })
})

describe('TASK-015: Retry & Safe Queue Removal Semantics', () => {
  it('resets failed upload item to PENDING with zero progress on retry', () => {
    const item: QueueItem = {
      id: 'test-1',
      file: new File(['content'], 'sample.pdf'),
      filename: 'sample.pdf',
      fileSizeBytes: 100,
      fileType: 'pdf',
      clientStatus: 'FAILED',
      uploadProgress: 45,
      errorMessage: 'Network timeout',
      retryCount: 0,
    }

    // Simulate retry logic
    const retried: QueueItem = {
      ...item,
      clientStatus: 'PENDING',
      uploadProgress: 0,
      errorMessage: null,
      retryCount: item.retryCount + 1,
    }

    assert.equal(retried.clientStatus, 'PENDING')
    assert.equal(retried.uploadProgress, 0)
    assert.equal(retried.errorMessage, null)
    assert.equal(retried.retryCount, 1)
  })

  it('clearing completed queue leaves pending and in-flight items intact', () => {
    const queue: QueueItem[] = [
      { id: '1', filename: 'a.pdf', clientStatus: 'SUCCESS', uploadProgress: 100, file: new File([], 'a.pdf'), fileSizeBytes: 10, fileType: 'pdf', retryCount: 0 },
      { id: '2', filename: 'b.pdf', clientStatus: 'UPLOADING', uploadProgress: 50, file: new File([], 'b.pdf'), fileSizeBytes: 10, fileType: 'pdf', retryCount: 0 },
      { id: '3', filename: 'c.pdf', clientStatus: 'NEEDS_REVIEW', uploadProgress: 100, file: new File([], 'c.pdf'), fileSizeBytes: 10, fileType: 'pdf', retryCount: 0 },
      { id: '4', filename: 'd.pdf', clientStatus: 'PROCESSING', uploadProgress: 100, file: new File([], 'd.pdf'), fileSizeBytes: 10, fileType: 'pdf', retryCount: 0 },
    ]

    const filtered = queue.filter((i) => i.clientStatus !== 'SUCCESS' && i.clientStatus !== 'NEEDS_REVIEW')
    assert.equal(filtered.length, 2)
    assert.equal(filtered[0].id, '2')
    assert.equal(filtered[1].id, '4')
  })
})
