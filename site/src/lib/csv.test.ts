import { describe, expect, it } from 'vitest';
import { exportFileName, parseCsv, sanitizeCsv, toCsv } from './csv';

describe('toCsv', () => {
  it('writes the header in column order and ends rows with CRLF', () => {
    const t = toCsv([{ b: 2, a: 1 }], ['a', 'b']);
    expect(t).toBe('a,b\r\n1,2\r\n');
  });
  it('quotes commas, quotes and newlines (RFC 4180)', () => {
    const t = toCsv([{ s: 'a,b', q: 'say "hi"', n: 'x\ny' }], ['s', 'q', 'n']);
    expect(t).toBe('s,q,n\r\n"a,b","say ""hi""","x\ny"\r\n');
  });
  it('writes null as empty and joins lists with semicolons', () => {
    expect(toCsv([{ a: null, b: ['x', 'y'] }], ['a', 'b'])).toBe('a,b\r\n,x;y\r\n');
  });
  it('writes only the header for no rows', () => {
    expect(toCsv([], ['a', 'b'])).toBe('a,b\r\n');
  });
});

describe('formula safety', () => {
  it('prefixes text that starts with a formula character', () => {
    expect(toCsv([{ a: '=HYPERLINK("x")' }], ['a'])).toBe('a\r\n"\'=HYPERLINK(""x"")"\r\n');
    expect(toCsv([{ a: '+1', b: '-x', c: '@sum', d: '\tx' }], ['a', 'b', 'c', 'd'])).toBe("a,b,c,d\r\n'+1,'-x,'@sum,'\tx\r\n");
  });
  it('leaves numbers and numeric text alone', () => {
    expect(toCsv([{ a: -5, b: '-73.95987' }], ['a', 'b'])).toBe('a,b\r\n-5,-73.95987\r\n');
  });
  it('parses and re-serializes a CSV text, sanitizing every field', () => {
    const src = 'id,street\n1,"=CMD|x"\n2,"A, B"\n';
    expect(parseCsv(src)).toEqual([['id', 'street'], ['1', '=CMD|x'], ['2', 'A, B']]);
    expect(sanitizeCsv(src)).toBe("id,street\r\n1,'=CMD|x\r\n2,\"A, B\"\r\n");
  });
});

describe('exportFileName', () => {
  it('slugs the area name and adds kind and date', () => {
    expect(exportFileName('Brooklyn CB 9', 'stretches', '2026-11-24')).toBe('brooklyn-cb-9-stretches-2026-11-24.csv');
    expect(exportFileName('Council District 40', 'blocks', '2026-11-24')).toBe('council-district-40-blocks-2026-11-24.csv');
    expect(exportFileName('Citywide', 'crashes', '2026-11-24')).toBe('citywide-crashes-2026-11-24.csv');
  });
});
