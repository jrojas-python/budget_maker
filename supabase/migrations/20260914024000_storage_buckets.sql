-- Buckets públicos requeridos por budget_maker.
-- No habilita escritura anónima; las operaciones de escritura usan únicamente service role.

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values
  (
    'products',
    'products',
    true,
    2097152,
    array['image/png', 'image/jpeg', 'image/webp']
  ),
  (
    'media',
    'media',
    true,
    2097152,
    array[
      'image/png',
      'image/jpeg',
      'image/jpg',
      'image/webp',
      'image/svg+xml',
      'image/x-icon',
      'image/vnd.microsoft.icon'
    ]
  )
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
