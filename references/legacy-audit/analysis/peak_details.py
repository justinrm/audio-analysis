"""Independent oversampling check and timestamp details; originals untouched."""
from pathlib import Path
import json
import numpy as np
from scipy.io import wavfile
from scipy import signal,ndimage
from scipy.spatial.distance import jensenshannon
ROOT=Path(__file__).resolve().parents[1]
R=json.loads((ROOT/'analysis/metrics.json').read_text());out=[]
for r in R:
 sr,raw=wavfile.read(ROOT/'upload'/r['filename']);x=raw.astype('float64')/2**31
 r['first_last_1s_rms_dbfs']=[float(10*np.log10(np.mean(x[:sr]**2))),float(10*np.log10(np.mean(x[-sr:]**2)))]
 r['last_50ms_rms_dbfs']=float(10*np.log10(np.mean(x[-sr//20:]**2)))
 full=(raw==-2**31)|(raw==2**31-256); loc=np.argwhere(full)
 runs=[]
 for ch in range(2):
  v=full[:,ch];d=np.diff(np.r_[False,v,False].astype(int));starts=np.flatnonzero(d==1);ends=np.flatnonzero(d==-1)
  runs.extend([{'time_s':float(s/sr),'channel':ch+1,'samples':int(e-s)} for s,e in zip(starts,ends)])
 over=[];maximum=(0.,0.,0);above=0
 for start in range(0,len(x),sr*5):
  end=min(start+sr*5,len(x)); left=max(0,start-128);right=min(len(x),end+128)
  up=signal.resample_poly(x[left:right],4,1,axis=0,window=('kaiser',8.6));up=up[(start-left)*4:(end-left)*4]
  k,c=np.unravel_index(np.argmax(np.abs(up)),up.shape);pk=float(abs(up[k,c]));tm=start/sr+k/(sr*4)
  if pk>maximum[0]:maximum=(pk,tm,int(c+1))
  if pk>1:over.append({'window_start_s':start/sr,'max_db':float(20*np.log10(pk)),'peak_s':tm})
  above+=int((np.abs(up)>1).sum())
 a=np.load(ROOT/'analysis'/f"{r['id']}_features.npz");t=a['rt'];rms=a['rms'];cor=a['cor'];sm=a['sm']
 windows=[]
 for start in range(0,int(r['duration_s']),10):
  sel=(t>=start)&(t<start+10)
  if sel.any():windows.append({'start':start,'rms_dbfs':float(10*np.log10(np.mean(10**(rms[sel]/10)))),'rms_median':float(np.median(rms[sel])),'cor_median':float(np.median(cor[sel])),'sm_median':float(np.median(sm[sel])),'onset_mean':float(np.mean(a['onset'][(a['onset_t']>=start)&(a['onset_t']<start+10)]))})
 smooth=ndimage.uniform_filter1d(rms,size=5);d=np.diff(smooth);ix=np.argsort(abs(d))[::-1];changes=[]
 for k in ix:
  if 5<t[k]<r['duration_s']-5 and all(abs(t[k]-v['time'])>8 for v in changes):changes.append({'time':float(t[k]),'five_second_smoothed_delta_db':float(d[k])})
  if len(changes)==6:break
 tail=[]
 for ms in [1000,500,100,50,10,1]:
  v=x[-int(sr*ms/1000):];tail.append({'last_ms':ms,'rms_dbfs':float(10*np.log10(np.mean(v*v))),'peak_dbfs':float(20*np.log10(np.max(np.abs(v))))})
 # Independent long-term peak chroma, intentionally different from time-average whitened chroma.
 f,ps=signal.welch(x.mean(axis=1),fs=sr,nperseg=32768,noverlap=16384)
 pp,_=signal.find_peaks(ps); keyvariants=[]
 major=np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]);minor=np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17]);names=['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B']
 for lo,hi in [(65,400),(200,2000),(65,2000)]:
  pk=pp[(f[pp]>=lo)&(f[pp]<=hi)];pc=np.round(69+12*np.log2(f[pk]/440)).astype(int)%12
  ch=np.array([np.sum(np.sqrt(ps[pk[pc==c]])) for c in range(12)]); ch/=ch.sum()
  rank=[]
  for mode,pf in [('major',major),('minor',minor)]:
   for k in range(12):rank.append({'key':names[k]+' '+mode,'r':float(np.corrcoef(ch,np.roll(pf,k))[0,1])})
  keyvariants.append({'band_hz':[lo,hi],'chroma':ch.tolist(),'top':sorted(rank,key=lambda v:v['r'],reverse=True)[:3]})
 out.append({'id':r['id'],'oversampled_peak_db':float(20*np.log10(maximum[0])),'oversampled_peak_time_s':maximum[1],'oversampled_peak_channel':maximum[2],'over_0db_5s_windows':over,'oversampled_values_above_1':above,'full_scale_runs':runs,'max_fullscale_run_samples':max([v['samples'] for v in runs],default=0),'ten_second_windows':windows,'strongest_smoothed_level_changes':changes,'min_corr_1s':float(min(cor)),'min_corr_time_s':float(t[np.argmin(cor)]),'negative_corr_seconds':int((cor<0).sum()),'last_fullscale_times_s':(loc[:,0]/sr).tolist(),'tail':tail,'key_sensitivity':keyvariants})
 print(r['id'],out[-1]['oversampled_peak_db'],out[-1]['oversampled_peak_time_s'],'rail samples',r['full_scale_samples'],'longest run',out[-1]['max_fullscale_run_samples'],flush=True)
 del x,raw,up
outp={'details':out,'pairs':[]}
for i in range(4):
 for j in range(i+1,4):
  p=np.array(R[i]['spectral_band_energy_percent'])/100;q=np.array(R[j]['spectral_band_energy_percent'])/100
  ca=np.array(R[i]['tonality']['pitch_class_mean']);cb=np.array(R[j]['tonality']['pitch_class_mean'])
  outp['pairs'].append({'a':R[i]['id'],'b':R[j]['id'],'spectral_js_distance_bits_sqrt':float(jensenshannon(p,q,base=2)),'chroma_cosine':float(ca@cb/(np.linalg.norm(ca)*np.linalg.norm(cb)))})
(ROOT/'analysis/details.json').write_text(json.dumps(outp,indent=2,allow_nan=False))
(ROOT/'analysis/metrics.json').write_text(json.dumps(R,indent=2,allow_nan=False))
