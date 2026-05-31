import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Det finnes lockfiler andre steder på maskinen (bl.a. ~/yarn.lock), så Next
  // gjetter feil workspace-rot. Lås tracing-roten til dette prosjektet.
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
