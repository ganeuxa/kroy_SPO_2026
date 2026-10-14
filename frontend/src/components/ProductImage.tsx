// Фото хранятся в MinIO, а он подключается на этапе III.
// Пока вместо фото показываем заглушку с первой буквой названия.
export default function ProductImage({ name }: { name: string; imageKey?: string | null }) {
  return (
    <div className="image-stub" aria-label={`Фото: ${name}`}>
      <span>{name.charAt(0)}</span>
    </div>
  );
}
