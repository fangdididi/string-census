export function ProjectHeader({ project, files }) {
  const subtitle = "You have " + files.length + " new files";
  const noun = files.length === 1 ? "" : "s";
  return (
    <header>
      <h1>{project.name}</h1>
      <p>{subtitle} · {new Date(project.updated).toLocaleDateString()}</p>
      <button aria-label="Trash icon" onClick={onDelete}>🗑</button>
    </header>
  );
}
