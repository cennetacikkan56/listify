-- Migration: Enterprise Panel - Listify
-- Mevcut şema zaten status ve teacher_feedback içeriyor.
-- Bu dosya referans amaçlıdır; gerekirse manuel çalıştırın.

-- StudentRecord: status (pending/approved/rejected), teacher_feedback - MEVCUT
-- ZORUNLU: Red nedeni için teacher_feedback kullanılıyor (Reddet = feedback zorunlu)

-- PostgreSQL (Render/Railway) için timezone uyumluluğu:
-- ALTER TABLE list_vera ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE;
-- ALTER TABLE assignment ALTER COLUMN due_date TYPE TIMESTAMP WITH TIME ZONE;

-- SQLite: Naive datetime kullanılıyor, timezone uygulama katmanında (Europe/Istanbul) yönetilir.
-- Ek sütun gerekmez.
