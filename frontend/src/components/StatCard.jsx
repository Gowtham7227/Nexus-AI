function StatCard({ title, value }) {
  return (
    <div
      style={{
        background: "#ffffff",
        borderRadius: "10px",
        padding: "20px",
        width: "220px",
        boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
      }}
    >
      <h3 style={{ color: "#555" }}>{title}</h3>
      <h1 style={{ color: "#2563eb" }}>{value}</h1>
    </div>
  );
}

export default StatCard;