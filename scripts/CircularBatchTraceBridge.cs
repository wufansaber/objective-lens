using System;
using ZOSAPI.Tools.RayTrace;

namespace ObjectiveLensCircularBridge {
    public static class CircularBatchTraceBridge {
        public static double[] Trace(IBatchRayTrace ray, int surface, double[] requests) {
            if (requests.Length % 5 != 0) throw new ArgumentException("Five values per ray required");
            int count = requests.Length / 5;
            var data = ray.CreateNormUnpol(count, RaysType.Real, surface);
            for (int i=0; i<count; i++) {
                int q=i*5;
                if (!data.AddRay((int)requests[q],requests[q+1],requests[q+2],requests[q+3],requests[q+4],OPDMode.None))
                    throw new InvalidOperationException("AddRay failed at "+i);
            }
            ray.RunAndWaitForCompletion();
            if (!data.StartReadingResults()) throw new InvalidOperationException("StartReadingResults failed");
            var result = new double[count*6];
            for (int i=0; i<count; i++) {
                int number,error,vignette;
                double x,y,z,l,m,n,lx,ly,lz,opd,intensity;
                bool ok=data.ReadNextResult(out number,out error,out vignette,out x,out y,out z,
                    out l,out m,out n,out lx,out ly,out lz,out opd,out intensity);
                if (!ok || number!=i+1 || error!=0 || vignette!=0)
                    throw new InvalidOperationException("Ray failure at surface "+surface+", request "+i+", error/vignette "+error+"/"+vignette);
                int q=i*6;
                result[q]=x;result[q+1]=y;result[q+2]=z;result[q+3]=l;result[q+4]=m;result[q+5]=n;
            }
            return result;
        }
    }
}
