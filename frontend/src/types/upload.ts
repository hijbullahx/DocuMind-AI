/**
 * TypeScript Data Models for Batch Drag-and-Drop Document Upload & Queue Processing.
 * Defines QueueItem, QueueItemStatus, PreflightValidationResult, and API Responses.
 */
import type { DocumentStatus, ValidationStatus } from './document'

export type QueueItemStatus =
  | 'PENDING'      // Queued in client, waiting for upload slot
  | 'VALIDATING'   // Pre-flight file validation in progress
  | 'UPLOADING'    // Active XMLHttpRequest payload transmission (0-100%)
  | 'QUEUED'       // Upload completed, server acknowledged with HTTP 201, Celery task queued
  | 'PROCESSING'   // Celery worker claimed task, extraction & validation in progress
  | 'SUCCESS'      // Celery pipeline finished with clean verification
  | 'NEEDS_REVIEW' // Celery pipeline finished, but flagged validation warnings/discrepancies
  | 'FAILED'       // Network upload error or server/worker processing failure

export interface QueueItem {
  id: string
  backendId?: string
  file: File
  filename: string
  fileSizeBytes: number
  fileType: string
  clientStatus: QueueItemStatus
  uploadProgress: number
  backendStatus?: DocumentStatus
  validationStatus?: ValidationStatus
  errorMessage?: string | null
  startedAt?: number
  completedAt?: number
  retryCount: number
}

export interface QueueSummary {
  total: number
  pending: number
  uploading: number
  processing: number
  verified: number
  needsReview: number
  failed: number
}

export interface PreflightValidationResult {
  isValid: boolean
  error?: string
}

export interface DocumentStatusResponse {
  id: string
  status: DocumentStatus
  validation_status: ValidationStatus
  error_message: string | null
  updated_at: string
}

export interface ReprocessResponse {
  message: string
  document_id: string
  status: DocumentStatus
  force: boolean
}
