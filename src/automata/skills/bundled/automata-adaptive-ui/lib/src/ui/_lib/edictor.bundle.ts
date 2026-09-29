import * as edictorModule from "edictor";

type EdictorModule = {
  defineField: typeof import("edictor").defineField;
  Model: typeof import("edictor").Model;
};

const moduleRecord = edictorModule as Record<string, unknown>;
const edictor = (
  "defineField" in moduleRecord
    ? moduleRecord
    : moduleRecord.default ?? moduleRecord["module.exports"]
) as EdictorModule;

/** Browser bundle entry for Edictor. */
export const defineField = edictor.defineField;
export const Model = edictor.Model;
