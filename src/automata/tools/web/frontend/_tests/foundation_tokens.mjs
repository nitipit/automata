/** Pure token/semantic contracts; no DOM, provider or private runtime data. */
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { converter, inGamut, wcagContrast } from 'culori';
const result = await build({
  stdin: { contents: `export * from './_tokens/color'; export * from './_theme/roles';`, resolveDir: new URL('../', import.meta.url).pathname, loader: 'ts' },
  bundle: true, platform: 'node', format: 'esm', write: false,
});
const { palette, shades, semanticRoles } = await import('data:text/javascript;base64,' + Buffer.from(result.outputFiles[0].text).toString('base64'));
const oklch = converter('oklch');
let colors = 0, pairs = 0, minimumText = Infinity, minimumNonText = Infinity;
assert.equal(Object.keys(palette).length, 15);
for (const [family, ramp] of Object.entries(palette)) {
  let previous = 2;
  for (const shade of shades) {
    const literal = ramp[shade];
    assert.match(literal, /^#[a-f\d]{6}$/i);
    assert.ok(inGamut('rgb')(literal), `${family}${shade} gamut`);
    const lightness = oklch(literal).l;
    assert.ok(lightness < previous, `${family} shades light-to-dark`);
    previous = lightness; colors++;
  }
  for (const mode of ['light', 'dark']) {
    const r = semanticRoles(mode, family);
    for (const [fg,bg] of [['text','surface'],['mutedText','surface'],['accentText','accent'],['error','errorSurface'],['success','successSurface'],['warning','warningSurface'],['info','infoSurface']]) {
      const contrast = wcagContrast(r[fg],r[bg]);
      assert.ok(contrast >= 4.5, `${mode}/${family} ${fg}/${bg}: ${contrast}`);
      minimumText = Math.min(minimumText, contrast); pairs++;
    }
    for (const fg of ['focus','border']) {
      const contrast = wcagContrast(r[fg],r.surface);
      assert.ok(contrast >= 3, `${mode}/${family} ${fg}/surface: ${contrast}`);
      minimumNonText = Math.min(minimumNonText, contrast); pairs++;
    }
  }
}
assert.equal(palette.neutral.white, '#ffffff'); assert.equal(palette.neutral.black, '#000000');
console.log(JSON.stringify({pass:true,colors:colors+2,semanticPairs:pairs,minimumTextContrast:minimumText,minimumNonTextContrast:minimumNonText}));
