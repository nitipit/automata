import { pathToFileURL } from "node:url";

export type StaticFileReader = (
  file: URL,
) => Promise<Uint8Array<ArrayBuffer> | null>;

export function fileFor(pathname: string, root: URL): URL | null {
  let decodedPath: string;
  try {
    decodedPath = decodeURIComponent(pathname);
  } catch {
    return null;
  }

  const segments = decodedPath.replaceAll("\\", "/").split("/");
  if (
    !pathname.startsWith("/") || decodedPath.includes("\0") ||
    segments.includes("..")
  ) {
    return null;
  }

  const relativePath = pathname.endsWith("/")
    ? `${pathname.slice(1)}index.html`
    : pathname.slice(1);
  if (!relativePath) {
    return null;
  }

  const file = new URL(relativePath, root);
  return file.href.startsWith(root.href) ? file : null;
}

export async function handleRequest(
  request: Request,
  root: URL,
  readFile: StaticFileReader = readStaticFile,
): Promise<Response> {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", {
      status: 405,
      headers: { allow: "GET, HEAD" },
    });
  }

  const lexicalFile = fileFor(new URL(request.url).pathname, root);
  if (!lexicalFile) {
    return new Response("Not found", { status: 404 });
  }

  const file = await resolvedFileFor(lexicalFile, root);
  if (!file) {
    return new Response("Not found", { status: 404 });
  }

  const content = await readFile(file);
  if (!content) {
    return new Response("Not found", { status: 404 });
  }

  return new Response(request.method === "HEAD" ? undefined : content, {
    headers: { "content-type": contentTypeFor(lexicalFile.pathname) },
  });
}

async function resolvedFileFor(
  file: URL,
  root: URL,
): Promise<URL | null> {
  try {
    const [rootPath, filePath] = await Promise.all([
      Deno.realPath(root),
      Deno.realPath(file),
    ]);
    const resolvedRoot = directoryUrl(pathToFileURL(rootPath));
    const resolvedFile = pathToFileURL(filePath);
    return resolvedFile.href.startsWith(resolvedRoot.href)
      ? resolvedFile
      : null;
  } catch (error) {
    if (
      error instanceof Deno.errors.NotFound ||
      error instanceof Deno.errors.NotADirectory ||
      error instanceof Deno.errors.PermissionDenied ||
      error instanceof Deno.errors.NotCapable
    ) {
      return null;
    }
    throw error;
  }
}

export function rootFor(args: string[]): URL {
  const value = args.find((argument) => argument.startsWith("--root="))
    ?.slice("--root=".length);
  if (!value) {
    throw new Error("--root=<website-directory> is required");
  }

  return directoryUrl(pathToFileURL(value));
}

if (import.meta.main) {
  const root = rootFor(Deno.args);
  const info = await Deno.stat(root);
  if (!info.isDirectory) {
    throw new Error(`Static root is not a directory: ${root.pathname}`);
  }

  const port = readPort(Deno.args);
  Deno.serve(
    { hostname: "127.0.0.1", port },
    (request) => handleRequest(request, root),
  );
}

function directoryUrl(url: URL): URL {
  if (!url.pathname.endsWith("/")) {
    url.pathname += "/";
  }
  return url;
}

async function readStaticFile(
  file: URL,
): Promise<Uint8Array<ArrayBuffer> | null> {
  try {
    const info = await Deno.stat(file);
    return info.isFile ? await Deno.readFile(file) : null;
  } catch (error) {
    if (error instanceof Deno.errors.NotFound) {
      return null;
    }
    throw error;
  }
}

function contentTypeFor(pathname: string): string {
  const extension = pathname.slice(pathname.lastIndexOf(".")).toLowerCase();
  const types: Record<string, string> = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
  };
  return types[extension] ?? "application/octet-stream";
}

function readPort(args: string[]): number {
  const value = args.find((argument) => argument.startsWith("--port="));
  const port = Number(value?.split("=", 2)[1] ?? "8765");

  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error("--port must be an integer from 1 through 65535");
  }

  return port;
}
