using System;
using ZOSAPI.Tools.RayTrace;

namespace ObjectiveLensBridge
{
    public static class BatchTraceBridge
    {
        public static double[] Trace(IBatchRayTrace ray, int surface, double[] requests)
        {
            if (requests.Length % 4 != 0) throw new ArgumentException("Four values per ray required");
            int count = requests.Length / 4;
            var data = ray.CreateNormUnpol(count, RaysType.Real, surface);
            for (int i = 0; i < count; i++)
            {
                int offset = i * 4;
                if (!data.AddRay((int)requests[offset], 0.0, requests[offset + 1],
                                 requests[offset + 2], requests[offset + 3], OPDMode.None))
                    throw new InvalidOperationException("AddRay failed at " + i);
            }
            ray.RunAndWaitForCompletion();
            if (!data.StartReadingResults()) throw new InvalidOperationException("StartReadingResults failed");
            var result = new double[count * 6];
            for (int i = 0; i < count; i++)
            {
                int number, error, vignette;
                double x, y, z, l, m, n, lx, ly, lz, opd, intensity;
                bool ok = data.ReadNextResult(out number, out error, out vignette,
                    out x, out y, out z, out l, out m, out n,
                    out lx, out ly, out lz, out opd, out intensity);
                if (!ok || number != i + 1 || error != 0 || vignette != 0)
                    throw new InvalidOperationException("Batch ray failed at " + i + ": " + error + "/" + vignette);
                int offset = i * 6;
                result[offset] = x; result[offset + 1] = y; result[offset + 2] = z;
                result[offset + 3] = l; result[offset + 4] = m; result[offset + 5] = n;
            }
            return result;
        }
    }
}
