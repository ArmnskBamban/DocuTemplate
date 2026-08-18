import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocuTemplate — Ubah laporan lama menjadi template baru",
  description:
    "Upload laporan praktikum contoh dan DocuTemplate akan membantu membersihkan isi lama tanpa merusak struktur dokumennya.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
