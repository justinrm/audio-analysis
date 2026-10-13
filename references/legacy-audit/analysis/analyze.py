"""Read-only WAV audit. Python 3 + numpy/scipy/matplotlib and FFmpeg required.
No listening, source separation, lyric transcription or learned genre model.
"""
import json, hashlib, subprocess, re, sys
from pathlib import Path
import numpy as np
from scipy import signal, ndimage
from scipy.io import wavfile
import scipy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis'; OUT.mkdir(exist_ok=True)
FILES=['Good Girl.wav','She Calls Me Back.wav','Nothing Holy Happens.wav','Hold Still.wav']
COLORS=['#2268a3','#c25c28','#448653','#8962ac']
def db(v): return 10*np.log10(np.maximum(v,1e-16))
def dbamp(v): return 20*np.log10(np.maximum(v,1e-16))
def blocks(x,n): return x[:len(x)//n*n].reshape(-1,n,*x.shape[1:])
def scalar(v): return float(v)
def ffprobe(p):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def loudness(p,idx):
 meta=OUT/f'{idx}_r128.txt'; log=OUT/f'{idx}_ffmpeg.log'
 proc=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(p),'-af',f'ebur128=metadata=1:peak=true,ametadata=print:file={meta}', '-f','null','-'],capture_output=True,text=True)
 log.write_text(proc.stderr); assert proc.returncode==0,proc.stderr
 records=[]; row=None
 for line in meta.read_text().splitlines():
  if line.startswith('frame:'):
   if row:records.append(row)
   row={'time':float(re.search(r'pts_time:(\S+)',line).group(1))}
  elif '=' in line and row is not None:
   k,v=line.split('=',1); row[k.replace('lavfi.r128.','')]=float(v)
 if row:records.append(row)
 summary=proc.stderr.split('Summary:')[-1]
 def read(pattern):return float(re.search(pattern,summary).group(1))
 measured={'integrated_lufs':read(r'I:\s*([-\d.]+) LUFS'),'lra_lu':read(r'LRA:\s*([-\d.]+) LU'),'true_peak_dbtp':read(r'True peak:\s*Peak:\s*([-\d.]+)')}
 measured['integrated_lufs_metadata']=records[-1]['I']
 measured['lra_lu_metadata']=records[-1]['LRA']
 # Independent FFmpeg 192-kHz loudnorm input-analysis cross-check, discarded output.
 pn=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(p),'-af','loudnorm=print_format=json','-f','null','-'],capture_output=True,text=True)
 assert pn.returncode==0
 check=json.loads(pn.stderr[pn.stderr.rfind('{'):]); (OUT/f'{idx}_loudnorm_input_check.json').write_text(json.dumps(check,indent=2))
 measured['loudnorm_input_check']={k:float(v) for k,v in check.items() if k.startswith('input_')}
 return measured,records

def rhythms(y,sr):
 f,t,z=signal.stft(y,fs=sr,nperseg=1024,noverlap=904,boundary=None,padded=False)
 mag=np.abs(z); log=np.log1p(100*mag)
 flux=np.maximum(np.diff(log,axis=1),0)
 onset=np.mean(flux[(f>=40)&(f<5500)],axis=0)
 onset=np.maximum(onset-ndimage.median_filter(onset,size=101),0)
 ot=t[1:]; dt=ot[1]-ot[0]
 def ac_candidates(o):
  o=o-o.mean(); ac=signal.correlate(o,o,mode='full',method='fft')[len(o)-1:]
  ac=ac/np.maximum(np.arange(len(o),0,-1),1); ac/=max(ac[0],1e-12)
  lo=int(60/200/dt); hi=int(60/45/dt)
  peaks,_=signal.find_peaks(ac[lo:hi],distance=3); peaks=peaks+lo
  peaks=sorted(peaks,key=lambda k:ac[k],reverse=True)[:6]
  return [{'bpm':float(60/(k*dt)),'acf':float(ac[k])} for k in peaks],ac
 cand,ac=ac_candidates(onset)
 local=[]
 for start in np.arange(0,len(y)/sr-20,20):
  c,_=ac_candidates(onset[(ot>=start)&(ot<start+20)])
  local.append({'start':float(start),'candidates':c[:3]})
 return {'candidates':cand,'local_20s':local,'onset_mean':float(onset.mean()),'onset_cv':float(onset.std()/max(onset.mean(),1e-12))},ot,onset,ac

MAJOR=np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
MINOR=np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
NAMES=['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B']
def keyrank(ch):
 out=[]
 for mode,profile in [('major',MAJOR),('minor',MINOR)]:
  for r in range(12):out.append({'key':NAMES[r]+' '+mode,'r':float(np.corrcoef(ch,np.roll(profile,r))[0,1])})
 return sorted(out,key=lambda a:a['r'],reverse=True)
def tonal(y,sr):
 f,t,z=signal.stft(y,fs=sr,nperseg=8192,noverlap=6992,boundary=None,padded=False)
 mag=np.abs(z).astype('float32'); del z
 h=ndimage.median_filter(mag,size=(1,31)); per=ndimage.median_filter(mag,size=(31,1))
 mask=h*h/(h*h+per*per+1e-15); harm=mag*mask
 # Local spectral whitening reduces broad timbral-envelope effects; still partial-sensitive.
 whiten=harm/(ndimage.median_filter(harm,size=(101,1))+1e-6)
 peaks=(harm>np.roll(harm,1,axis=0))&(harm>=np.roll(harm,-1,axis=0))
 idx=(f>=65)&(f<=2000)
 midi=69+12*np.log2(f[idx]/440)
 weights=(np.sqrt(harm[idx])*np.minimum(whiten[idx],20))*peaks[idx]
 # Estimate tuning from strong, interpolated spectral peaks in average spectrum.
 avg=harm.mean(axis=1); pk,_=signal.find_peaks(avg)
 pk=pk[(f[pk]>=100)&(f[pk]<=1500)]
 lg=np.log(np.maximum(avg,1e-12)); delta=.5*(lg[pk-1]-lg[pk+1])/(lg[pk-1]-2*lg[pk]+lg[pk+1]+1e-12)
 freq=(pk+np.clip(delta,-.5,.5))*sr/8192
 cents=(1200*np.log2(freq/440)+50)%100-50
 hist=np.array([np.sum(avg[pk]*np.exp(-((cents-c)/8)**2)) for c in range(-50,51)])
 tuning=float(np.argmax(hist)-50)
 pc=np.round(midi-tuning/100).astype(int)%12
 chroma=np.stack([weights[pc==c].sum(axis=0) for c in range(12)])
 chroma/=np.maximum(chroma.sum(axis=0),1e-12)
 mean=chroma.mean(axis=1); rawrank=keyrank(mean)
 segments=[]
 for start in np.arange(0,len(y)/sr-12,20):
  c=chroma[:,(t>=start)&(t<start+20)].mean(axis=1)
  segments.append({'start':float(start),'top':keyrank(c)[:3]})
 return {'pitch_class_mean':mean.tolist(),'key_candidates':rawrank[:6],'tuning_offset_cents_est':tuning,'local_20s':segments},t,chroma

results=[]; arrays={}
for i,name in enumerate(FILES):
 idx=chr(65+i); p=ROOT/'upload'/name; print('Analyzing',idx,flush=True)
 probe=ffprobe(p); sr,raw=wavfile.read(p); s=probe['streams'][0]
 assert raw.ndim==2 and raw.shape[1]==2
 x=raw.astype(np.float64)/(2**31 if raw.dtype==np.int32 else 2**15)
 dur=len(x)/sr; assert abs(dur-float(s['duration']))<1/sr
 assert np.isfinite(x).all()
 m=x.mean(axis=1); side=(x[:,0]-x[:,1])/2
 energy=np.mean(x*x); peak=float(np.max(np.abs(x)))
 r={'id':idx,'filename':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'duration_s':dur,'sample_rate':sr,'channels':2,'bit_depth':s['bits_per_sample'],'samples_per_channel':len(x),'decode':'complete; header and decoded duration agree','metadata':probe['format'].get('tags',{}),'sample_peak_dbfs':float(dbamp(peak)),'rms_dbfs':float(db(energy)),'crest_db':float(dbamp(peak)-db(energy)),'dc_l_r':x.mean(axis=0).tolist(),'full_scale_samples':int(((raw==-2**31)|(raw==2**31-256)).sum()),'samples_above_minus_0_1_dbfs':int((np.abs(x)>10**(-.1/20)).sum()),'lr_correlation':float(np.corrcoef(x.T)[0,1]),'side_mid_db':float(db(np.mean(side**2)/np.mean(m**2))),'side_energy_percent':float(np.mean(side**2)/energy*100),'mono_energy_change_db':float(db(np.mean(m*m)/energy))}
 r.update(dict(zip(['loudness','r128_records'],loudness(p,idx))))
 r['short_term_p10_p90_lufs']=np.percentile([a['S'] for a in r['r128_records'] if a['time']>=3 and a['S']>-45],[10,90]).tolist()
 n=sr; bx=blocks(x,n); rms=db(np.mean(bx**2,axis=(1,2))); rt=np.arange(len(rms))+.5
 cor=[]; sm=[]
 for b in bx:
  cor.append(float(np.corrcoef(b.T)[0,1])); bm=b.mean(axis=1);bs=(b[:,0]-b[:,1])/2;sm.append(float(db(np.mean(bs*bs)/np.mean(bm*bm))))
 frame50=db(np.mean(blocks(x,sr//20)**2,axis=(1,2)))
 r['silence_50ms_below_minus60_s']=float(np.sum(frame50<-60)*.05)
 r['first_last_1s_rms_dbfs']=[float(db(np.mean(x[:sr]**2))),float(db(np.mean(x[-sr:]**2)))]
 r['last_sample_l_r']=x[-1].tolist()
 r['last_50ms_rms_dbfs']=float(db(np.mean(x[-sr//20:]**2)))
 r['one_second_rms_extrema']={'max_s':float(rt[np.argmax(rms)]),'max_dbfs':float(max(rms)),'min_interior_s':float(rt[5:-5][np.argmin(rms[5:-5])]),'min_interior_dbfs':float(min(rms[5:-5]))}
 # Full-band stereo PSD: average channel power, not mono fold-down.
 f,ps=signal.welch(x,fs=sr,nperseg=8192,noverlap=4096,axis=0); ps=ps.mean(axis=1)
 edges=[0,20,60,120,250,500,2000,5000,10000,24001]
 bands=[]
 for lo,hi in zip(edges[:-1],edges[1:]):bands.append(float(ps[(f>=lo)&(f<hi)].sum()/ps.sum()*100))
 r['spectral_band_edges_hz']=edges;r['spectral_band_energy_percent']=bands
 r['power_weighted_centroid_hz']=float((f*ps).sum()/ps.sum())
 # Magnitude centroid distribution on short frames, separate from power centroid.
 f2,t2,z=signal.stft(m,fs=sr,nperseg=2048,noverlap=1024,boundary=None,padded=False)
 mag=np.abs(z);cent=(f2[:,None]*mag).sum(axis=0)/np.maximum(mag.sum(axis=0),1e-12)
 r['magnitude_centroid_median_hz']=float(np.median(cent)); del z,mag
 low=signal.sosfilt(signal.butter(6,120,fs=sr,output='sos'),x,axis=0)
 r['below_120hz_lr_correlation']=float(np.corrcoef(low.T)[0,1])
 lm=low.mean(axis=1);ls=(low[:,0]-low[:,1])/2
 r['below_120hz_side_mid_db']=float(db(np.mean(ls*ls)/np.mean(lm*lm)));del low,lm,ls
 y=signal.resample_poly(m,1,4); sr2=sr//4
 rhythm,ot,onset,ac=rhythms(y,sr2);r['rhythm']=rhythm
 ton,ct,chroma=tonal(y,sr2);r['tonality']=ton
 # Two-second analysis bins; feature transition = dissimilarity of 6-s means.
 ff,tt,zz=signal.stft(y,fs=sr2,nperseg=2048,noverlap=1448,boundary=None,padded=False)
 pp=np.abs(zz)**2; del zz
 freqedges=np.geomspace(40,5500,33)
 spec=np.stack([pp[(ff>=a)&(ff<b)].mean(axis=0) for a,b in zip(freqedges[:-1],freqedges[1:])])
 bt=np.arange(1,dur-1,2); logs=[];chs=[]; ons=[]
 for t0 in bt:
  logs.append(np.log10(np.maximum(spec[:,(tt>=t0-1)&(tt<t0+1)].mean(axis=1),1e-12)))
  chs.append(chroma[:,(ct>=t0-1)&(ct<t0+1)].mean(axis=1));ons.append(onset[(ot>=t0-1)&(ot<t0+1)].mean())
 logs=np.array(logs);chs=np.array(chs);ons=np.array(ons)
 # Relative spectral shape removes level from timbral recurrence.
 shape=logs-logs.mean(axis=1,keepdims=True)
 feat=np.column_stack([shape,chs*3])
 norm=(feat-feat.mean(axis=0))/np.maximum(feat.std(axis=0),.15)
 novel=np.zeros(len(bt))
 for k in range(3,len(bt)-3):novel[k]=np.linalg.norm(norm[k:k+3].mean(axis=0)-norm[k-3:k].mean(axis=0))/np.sqrt(norm.shape[1])
 peakidx,_=signal.find_peaks(novel,distance=4,prominence=.18)
 peakidx=sorted(peakidx,key=lambda k:novel[k],reverse=True)[:12]; peakidx=sorted(peakidx)
 r['feature_transition_candidates_s']=[float(bt[k]-1) for k in peakidx]
 # Similarity is relative, within-track cosine of centered log spectra and chroma.
 feat2=np.column_stack([shape,chs*3]);feat2=feat2-feat2.mean(axis=0)
 feat2/=np.maximum(np.linalg.norm(feat2,axis=1,keepdims=True),1e-12)
 sim=feat2@feat2.T
 # 12-s recurrence patches, exclude <20-s displacements; top distinct pairs.
 rec=[]
 for a in range(2,len(bt)-6):
  for b in range(a+10,len(bt)-6):
   score=float(np.mean([sim[a+k,b+k] for k in range(6)]))
   rec.append((score,a,b))
 chosen=[]
 for score,a,b in sorted(rec,reverse=True):
  if all(abs(a-u)>6 or abs(b-v)>6 for _,u,v in chosen):chosen.append((score,a,b))
  if len(chosen)==5:break
 r['recurrence_12s_candidates']=[{'a_start':float(bt[a]-1),'b_start':float(bt[b]-1),'relative_feature_cosine':score} for score,a,b in chosen]
 r['thirds_rms_dbfs']=[float(db(np.mean(part**2))) for part in np.array_split(x,3)]
 arrays[idx]={'rt':rt,'rms':rms,'cor':np.array(cor),'sm':np.array(sm),'freq':f,'psd':ps,'onset_t':ot,'onset':onset,'acf':ac,'chroma_t':ct,'chroma':chroma,'bin_t':bt,'novelty':novel,'similarity':sim,'shape':shape,'onset_bin':ons}
 np.savez_compressed(OUT/f'{idx}_features.npz',**arrays[idx])
 results.append(r)
 (OUT/'metrics.json').write_text(json.dumps(results,indent=2,allow_nan=False))
 del x,m,side,raw,y,pp,spec,chroma
 print(idx,'done',r['loudness'],r['rhythm']['candidates'][:3],r['tonality']['key_candidates'][:3],flush=True)

style={'axes.spines.top':False,'axes.spines.right':False,'font.size':10,'figure.facecolor':'white'}
plt.rcParams.update(style)
fig,ax=plt.subplots(4,1,figsize=(12,10),sharex=True)
for k,r in enumerate(results):
 a=arrays[r['id']]; records=r['r128_records'];ts=np.array([v['time'] for v in records]);st=np.array([v['S'] for v in records])
 ax[k].plot(a['rt'],a['rms'],color=COLORS[k],lw=.8,label='1-s RMS (dBFS)')
 good=(ts>=3)&(st>-60);ax[k].plot(ts[good]-1.4,st[good],color='#222222',lw=1,label='3-s short-term loudness (LUFS; centered)')
 ax[k].set_title(r['filename'],loc='left');ax[k].set_ylim(-45,-5);ax[k].grid(alpha=.2);ax[k].set_ylabel('dBFS / LUFS')
 for t0 in r['feature_transition_candidates_s']:ax[k].axvline(t0,color=COLORS[k],alpha=.2)
ax[0].legend(loc='lower center',ncol=2,fontsize=8);ax[-1].set_xlabel('Seconds from file start');fig.suptitle('Energy and loudness: common absolute scales; faint lines = estimated feature transitions')
fig.tight_layout();fig.savefig(ROOT/'output'/'energy_loudness.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(12,4))
for i,r in enumerate(results):
 a=arrays[r['id']]; ps=a['psd']; df=a['freq'][1]-a['freq'][0]
 norm=ps/(ps.sum()*df); smooth=ndimage.gaussian_filter1d(norm,3)
 axs[0].semilogx(a['freq'][1:],db(smooth[1:]),label=r['filename'][:-4],color=COLORS[i])
 axs[1].plot(np.arange(9),r['spectral_band_energy_percent'],marker='o',label=r['filename'][:-4],color=COLORS[i])
axs[0].set(xlim=(20,24000),ylim=(-85,-20),xlabel='Frequency (Hz)',ylabel='Normalized PSD (dB per Hz)',title='Level-independent long-term spectral shape')
axs[1].set_xticks(np.arange(9),['<20','20-60','60-120','120-250','250-500','0.5-2k','2-5k','5-10k','10-24k'],rotation=40);axs[1].set(ylabel='Percent of analyzed power',title='Stereo-average spectral-band energy')
for ax0 in axs:ax0.grid(alpha=.2)
axs[0].legend(fontsize=8);fig.tight_layout();fig.savefig(ROOT/'output'/'spectral.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(1,3,figsize=(12,4));names=[r['filename'][:-4] for r in results]
for ax0,key,title,unit in zip(axs,['integrated_lufs','lra_lu','true_peak_dbtp'],['Integrated loudness','Loudness range','True peak'],['LUFS','LU','dBTP']):
 vals=[r['loudness'][key] for r in results];ax0.bar(np.arange(4),vals,color=COLORS);ax0.set_xticks(np.arange(4),names,rotation=35,ha='right');ax0.set(title=title,ylabel=unit)
 for i,v in enumerate(vals):ax0.annotate(f'{v:.1f}',(i,v),xytext=(0,5 if v>=0 else -14),textcoords='offset points',ha='center')
 ax0.margins(y=.18);ax0.grid(axis='y',alpha=.2)
fig.tight_layout();fig.savefig(ROOT/'output'/'mastering.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(2,1,figsize=(12,6),sharex=True)
for i,r in enumerate(results):
 a=arrays[r['id']];axs[0].plot(a['rt'],ndimage.median_filter(a['cor'],size=5),label=names[i],color=COLORS[i]);axs[1].plot(a['rt'],ndimage.median_filter(a['sm'],size=5),color=COLORS[i])
axs[0].set(ylabel='L/R correlation',ylim=(-.2,1),title='Stereo evolution: 1-s windows, 5-s median display smoothing');axs[1].set(ylabel='Side / mid (dB)',xlabel='Seconds from file start',ylim=(-35,5));axs[0].axhline(0,color='black',lw=.7);axs[0].legend(ncol=2,fontsize=8)
for ax0 in axs:ax0.grid(alpha=.2)
fig.tight_layout();fig.savefig(ROOT/'output'/'stereo.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(2,2,figsize=(10,9))
for ax0,r in zip(axs.flat,results):
 a=arrays[r['id']];im=ax0.imshow(a['similarity'],origin='lower',extent=(0,r['duration_s'],0,r['duration_s']),vmin=-1,vmax=1,cmap='RdBu_r',aspect='auto');ax0.set(title=r['filename'],xlabel='Time (s)',ylabel='Time (s)')
fig.colorbar(im,ax=axs.ravel().tolist(),shrink=.75,label='Centered feature cosine; not melody similarity');fig.suptitle('Within-track timbral / pitch-class recurrence (2-s bins)');fig.subplots_adjust(top=.92,hspace=.3,wspace=.3,right=.85);fig.savefig(ROOT/'output'/'recurrence.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(12,4))
for i,r in enumerate(results):
 a=arrays[r['id']];lags=np.arange(len(a['acf']))*.01;sel=(lags>=.3)&(lags<=1.33);axs[0].plot(60/lags[sel],a['acf'][sel],color=COLORS[i],label=names[i]);axs[1].plot(np.arange(12),r['tonality']['pitch_class_mean'],marker='o',color=COLORS[i])
axs[0].set(xlabel='Pulse-rate candidate (BPM)',ylabel='Normalized onset autocorrelation',title='Algorithmic pulse evidence; meter / half-time unresolved',xlim=(45,200));axs[0].legend(fontsize=8);axs[1].set_xticks(np.arange(12),NAMES);axs[1].set(ylabel='Relative peak-weighted chroma',title='Pitch-class profiles; partial-sensitive estimates')
for ax0 in axs:ax0.grid(alpha=.2)
fig.tight_layout();fig.savefig(ROOT/'output'/'rhythm_tonality.png',dpi=170);plt.close(fig)
versions={'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'matplotlib':matplotlib.__version__,'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0]}
(OUT/'versions.json').write_text(json.dumps(versions,indent=2))
print('Completed all analyses and plots',flush=True)
