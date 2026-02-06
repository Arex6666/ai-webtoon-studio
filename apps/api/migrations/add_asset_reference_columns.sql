-- 添加 Asset 表缺失的字段 (S5-01)
-- 执行方式: psql -U postgres -d webtoon_studio -f add_asset_reference_columns.sql

-- 检查字段是否已存在，如果不存在则添加
DO $$
BEGIN
    -- 添加 reference_image_path
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'assets' AND column_name = 'reference_image_path'
    ) THEN
        ALTER TABLE assets ADD COLUMN reference_image_path VARCHAR(512);
        RAISE NOTICE 'Added column reference_image_path';
    ELSE
        RAISE NOTICE 'Column reference_image_path already exists';
    END IF;

    -- 添加 reference_image_status
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'assets' AND column_name = 'reference_image_status'
    ) THEN
        ALTER TABLE assets ADD COLUMN reference_image_status VARCHAR(50) DEFAULT 'none';
        RAISE NOTICE 'Added column reference_image_status';
    ELSE
        RAISE NOTICE 'Column reference_image_status already exists';
    END IF;

    -- 添加 reference_image_meta
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'assets' AND column_name = 'reference_image_meta'
    ) THEN
        ALTER TABLE assets ADD COLUMN reference_image_meta JSONB;
        RAISE NOTICE 'Added column reference_image_meta';
    ELSE
        RAISE NOTICE 'Column reference_image_meta already exists';
    END IF;
END $$;

-- 更新现有记录的默认值
UPDATE assets
SET reference_image_status = 'none'
WHERE reference_image_status IS NULL;

-- 验证
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'assets'
    AND column_name IN ('reference_image_path', 'reference_image_status', 'reference_image_meta')
ORDER BY column_name;
