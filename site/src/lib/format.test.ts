import { describe, expect, it } from 'vitest';
import { areaLabel, areaTag, fmtDate, fmtEnds, fmtInt, fmtScore, matchArea, titleCase } from './format';
import type { Area } from './types';

const area = (id: string, name: string, kind: 'cb' | 'cd' = 'cb', borough: string | null = 'Brooklyn') =>
  ({ kind, id, name, borough } as Area);

describe('format', () => {
  it('fmtInt', () => { expect(fmtInt(12345)).toBe('12,345'); expect(fmtInt(0)).toBe('0'); });
  it('fmtScore', () => { expect(fmtScore(22.54)).toBe('22.5'); expect(fmtScore(3)).toBe('3.0'); });
  it('fmtDate', () => { expect(fmtDate('2026-11-24')).toBe('Nov 24, 2026'); expect(fmtDate('2026-01-05')).toBe('Jan 5, 2026'); });
  it('areaLabel', () => expect(areaLabel(area('309', 'Brooklyn CB 9'))).toBe('Brooklyn CB 9'));
  it('areaTag', () => {
    expect(areaTag('cb', '309')).toBe('CB 9');
    expect(areaTag('cb', '317')).toBe('CB 17');
    expect(areaTag('cd', '40')).toBe('CD 40');
  });
  it('titleCase', () => {
    expect(titleCase('EMPIRE BOULEVARD')).toBe('Empire Boulevard');
    expect(titleCase('EAST 1ST STREET')).toBe('East 1st Street');
    expect(titleCase("ST. JOHN'S PLACE")).toBe("St. John's Place");
  });
  it('fmtEnds never shows null', () => {
    expect(fmtEnds('KINGS HWY', null)).toBe('Kings Hwy → continues');
    expect(fmtEnds(null, 'A ST')).toBe('continues → A St');
    expect(fmtEnds(null, null)).toBe('continues → continues');
  });
  it('matchArea', () => {
    const list = [area('308', 'Brooklyn CB 8'), area('309', 'Brooklyn CB 9'), area('317', 'Brooklyn CB 17')];
    expect(matchArea(list, 'brooklyn 9').map((a) => a.id)).toEqual(['309']);
    expect(matchArea(list, '17').map((a) => a.id)).toEqual(['317']);
    expect(matchArea(list, '').length).toBe(3);
    const cds = [area('35', 'Council District 35', 'cd', null), area('40', 'Council District 40', 'cd', null)];
    expect(matchArea(cds, '40').map((a) => a.id)).toEqual(['40']);
  });
});
