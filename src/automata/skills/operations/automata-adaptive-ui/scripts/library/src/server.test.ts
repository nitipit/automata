import { fileFor, handleRequest, rootFor } from "./server.ts";

const lexicalRoot = new URL("file:///runtime/session/");

Deno.test("static host maps selected-root files and rejects traversal", () => {
  assert(fileFor("/", lexicalRoot)?.pathname === "/runtime/session/index.html");
  assert(
    fileFor("/adaptive-ui.js", lexicalRoot)?.pathname ===
      "/runtime/session/adaptive-ui.js",
  );
  assert(
    fileFor("/nested/page.js", lexicalRoot)?.pathname ===
      "/runtime/session/nested/page.js",
  );

  for (
    const pathname of [
      "/../source.ts",
      "/%2e%2e/source.ts",
      "/..%2fsource.ts",
      "/bad%ZZ",
    ]
  ) {
    assert(
      fileFor(pathname, lexicalRoot) === null,
      `Expected ${pathname} to be rejected`,
    );
  }
});

Deno.test("static host requires an explicit relative or absolute root", () => {
  let message = "";
  try {
    rootFor([]);
  } catch (error) {
    message = error instanceof Error ? error.message : String(error);
  }
  assert(message.includes("--root=<website-directory> is required"));
  assert(rootFor(["--root=/tmp/session"]).pathname === "/tmp/session/");
  assert(
    rootFor(["--root=relative-session"]).pathname.endsWith(
      "/relative-session/",
    ),
  );
});

Deno.test("static host serves ordinary real files with MIME types", async () => {
  await withTestTree(async ({ rootPath, root }) => {
    await Deno.mkdir(`${rootPath}/assets`);
    await Deno.writeTextFile(`${rootPath}/index.html`, "<h1>Adaptive UI</h1>");
    await Deno.writeTextFile(`${rootPath}/assets/adaptive-ui.js`, "export {};");
    await Deno.writeTextFile(`${rootPath}/assets/style.css`, "body {}");
    await Deno.writeFile(
      `${rootPath}/assets/asset.bin`,
      new Uint8Array([0, 1]),
    );

    const page = await handleRequest(new Request("http://localhost/"), root);
    assert(page.status === 200);
    assert(page.headers.get("content-type") === "text/html; charset=utf-8");
    assert(await page.text() === "<h1>Adaptive UI</h1>");

    const script = await handleRequest(
      new Request("http://localhost/assets/adaptive-ui.js", {
        method: "HEAD",
      }),
      root,
    );
    assert(script.status === 200);
    assert(
      script.headers.get("content-type") === "text/javascript; charset=utf-8",
    );
    assert(script.body === null);

    const style = await handleRequest(
      new Request("http://localhost/assets/style.css"),
      root,
    );
    assert(style.status === 200);
    assert(style.headers.get("content-type") === "text/css; charset=utf-8");

    const binary = await handleRequest(
      new Request("http://localhost/assets/asset.bin"),
      root,
    );
    assert(binary.status === 200);
    assert(binary.headers.get("content-type") === "application/octet-stream");
  });
});

Deno.test("one website serves shared library and independent session subpages", async () => {
  await withTestTree(async ({ rootPath, root }) => {
    await Deno.mkdir(`${rootPath}/lib`);
    await Deno.writeTextFile(
      `${rootPath}/lib/adaptive-ui.js`,
      "export const version = 1;",
    );
    for (const name of ["dashboard", "report"]) {
      await Deno.mkdir(`${rootPath}/sessions/${name}/images`, {
        recursive: true,
      });
      await Deno.writeTextFile(
        `${rootPath}/sessions/${name}/index.html`,
        `<script type="module">import '/lib/adaptive-ui.js';</script><h1>${name}</h1>`,
      );
      await Deno.writeTextFile(
        `${rootPath}/sessions/${name}/images/chart.svg`,
        "<svg/>",
      );
      const response = await handleRequest(
        new Request(`http://localhost/sessions/${name}/`),
        root,
      );
      assert(response.status === 200);
      assert((await response.text()).includes(`<h1>${name}</h1>`));
      const asset = await handleRequest(
        new Request(`http://localhost/sessions/${name}/images/chart.svg`),
        root,
      );
      assert(asset.status === 200);
      assert(asset.headers.get("content-type") === "image/svg+xml");
    }
    const library = await handleRequest(
      new Request("http://localhost/lib/adaptive-ui.js"),
      root,
    );
    assert(await library.text() === "export const version = 1;");
    await Deno.writeTextFile(
      `${rootPath}/lib/adaptive-ui.js`,
      "export const version = 2;",
    );
    const updated = await handleRequest(
      new Request("http://localhost/lib/adaptive-ui.js"),
      root,
    );
    assert(await updated.text() === "export const version = 2;");
  });
});

Deno.test({
  name: "static host rejects a file symlink escaping the selected root",
  ignore: Deno.build.os === "windows",
  fn: async () => {
    await withTestTree(async ({ outsidePath, rootPath, root }) => {
      await Deno.writeTextFile(`${outsidePath}/outside.txt`, "outside");
      await Deno.symlink(
        `${outsidePath}/outside.txt`,
        `${rootPath}/outside-file.txt`,
      );

      const response = await handleRequest(
        new Request("http://localhost/outside-file.txt"),
        root,
      );
      assert(response.status === 404);
      assert(await response.text() === "Not found");
    });
  },
});

Deno.test({
  name: "static host rejects a directory symlink escaping the selected root",
  ignore: Deno.build.os === "windows",
  fn: async () => {
    await withTestTree(async ({ outsidePath, rootPath, root }) => {
      await Deno.writeTextFile(`${outsidePath}/outside.txt`, "outside");
      await Deno.symlink(outsidePath, `${rootPath}/outside-directory`, {
        type: "dir",
      });

      const response = await handleRequest(
        new Request("http://localhost/outside-directory/outside.txt"),
        root,
      );
      assert(response.status === 404);
      assert(await response.text() === "Not found");
    });
  },
});

Deno.test("static host returns deterministic missing-file and method responses", async () => {
  await withTestTree(async ({ root }) => {
    const missing = await handleRequest(
      new Request("http://localhost/missing.txt"),
      root,
    );
    assert(missing.status === 404);
    assert(await missing.text() === "Not found");
  });

  let readAttempted = false;
  const method = await handleRequest(
    new Request("http://localhost/", { method: "POST" }),
    lexicalRoot,
    () => {
      readAttempted = true;
      return Promise.resolve(new TextEncoder().encode("unexpected"));
    },
  );
  assert(method.status === 405);
  assert(method.headers.get("allow") === "GET, HEAD");
  assert(!readAttempted, "Unsupported methods must not read static files");
});

type TestTree = {
  outsidePath: string;
  rootPath: string;
  root: URL;
};

async function withTestTree(
  run: (tree: TestTree) => Promise<void>,
): Promise<void> {
  const basePath = await Deno.makeTempDir({
    dir: ".",
    prefix: ".server-test-",
  });
  const rootPath = `${basePath}/root`;
  const outsidePath = `${basePath}/outside`;

  try {
    await Deno.mkdir(rootPath);
    await Deno.mkdir(outsidePath);
    await run({
      outsidePath,
      rootPath,
      root: rootFor([`--root=${rootPath}`]),
    });
  } finally {
    await Deno.remove(basePath, { recursive: true });
  }
}

function assert(
  condition: unknown,
  message = "Assertion failed",
): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}
