export default function CreateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="font-sans antialiased" style={{ minHeight: "100vh", backgroundColor: "#050505", color: "rgba(255,255,255,0.87)" }}>
      {children}
    </div>
  );
}
