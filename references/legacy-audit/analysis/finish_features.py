import json,numpy as np
from pathlib import Path
from scipy.io import wavfile
from scipy import signal,ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];R=json.loads((ROOT/'analysis/metrics.json').read_text());D=json.loads((ROOT/'analysis/details.json').read_text())
for r,d in zip(R,D['details']):
 a=np.load(ROOT/'analysis'/f"{r['id']}_features.npz"); ac=a['acf'];dt=float(np.median(np.diff(a['onset_t'])))
 for c in r['rhythm']['candidates']:
  k=int(round(60/c['bpm']/dt));frac=.5*(ac[k-1]-ac[k+1])/(ac[k-1]-2*ac[k]+ac[k+1]);c['interpolated_bpm']=float(60/((k+frac)*dt))
 k=np.argmin(a['cor']);d['min_corr_rms_dbfs']=float(a['rms'][k]);d['min_corr_side_mid_db']=float(a['sm'][k]);d['min_corr_mono_energy_change_db']=float(-10*np.log10(1+10**(a['sm'][k]/10)))
 sr,raw=wavfile.read(ROOT/'upload'/r['filename']);x=raw.astype('float64')/2**31
 # Silence is a threshold event, not proof of absence of all sources.
 n=sr//20;v=x[:len(x)//n*n].reshape(-1,n,2);level=10*np.log10(np.maximum(np.mean(v*v,axis=(1,2)),1e-16));q=level<-60;diff=np.diff(np.r_[False,q,False].astype(int));s=np.flatnonzero(diff==1);e=np.flatnonzero(diff==-1)
 d['below_minus60_50ms_runs']=[{'start_s':float(i*.05),'end_s':float(j*.05)} for i,j in zip(s,e)]
 del x,raw,v
for p in D['pairs']:
 ar=next(r for r in R if r['id']==p['a']);br=next(r for r in R if r['id']==p['b']);aa=np.load(ROOT/'analysis'/f"{p['a']}_features.npz");bb=np.load(ROOT/'analysis'/f"{p['b']}_features.npz")
 phase=np.linspace(.05,.95,91);ea=np.interp(phase,aa['rt']/ar['duration_s'],ndimage.uniform_filter1d(aa['rms'],size=5));eb=np.interp(phase,bb['rt']/br['duration_s'],ndimage.uniform_filter1d(bb['rms'],size=5));p['relative_time_energy_pearson']=float(np.corrcoef(ea,eb)[0,1])
(ROOT/'analysis/metrics.json').write_text(json.dumps(R,indent=2,allow_nan=False));(ROOT/'analysis/details.json').write_text(json.dumps(D,indent=2,allow_nan=False))
colors=['#2268a3','#c25c28','#448653','#8962ac']
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
fig,axs=plt.subplots(2,2,figsize=(11,9))
for ax,r in zip(axs.flat,R):
 a=np.load(ROOT/'analysis'/f"{r['id']}_features.npz");bt=a['bin_t'];im=ax.imshow(a['similarity'],origin='lower',extent=(bt[0]-1,bt[-1]+1,bt[0]-1,bt[-1]+1),vmin=-1,vmax=1,cmap='RdBu_r',aspect='auto');ax.set(title=r['filename'],xlabel='Time (s)',ylabel='Time (s)')
fig.subplots_adjust(top=.91,hspace=.3,wspace=.3,right=.84);ca=fig.add_axes([.88,.15,.025,.65]);fig.colorbar(im,cax=ca,label='Centered feature cosine; not melody similarity');fig.suptitle('Within-track timbral / pitch-class recurrence (2-s bins)');fig.savefig(ROOT/'output/recurrence.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(4,1,figsize=(12,7),sharex=True)
for i,(ax,r) in enumerate(zip(axs,R)):
 a=np.load(ROOT/'analysis'/f"{r['id']}_features.npz");bounds=[0]+r['feature_transition_candidates_s']+[r['duration_s']]
 for j,(s,e) in enumerate(zip(bounds[:-1],bounds[1:])):
  ax.broken_barh([(s,e-s)],(.1,.8),facecolors=colors[i],alpha=.25 if j%2 else .65);ax.text((s+e)/2,.5,str(j+1),ha='center',va='center')
 ax.plot(a['bin_t'],a['novelty']/max(a['novelty'].max(),1e-6)*.7+.1,color='#222',lw=1);ax.set_ylim(0,1);ax.set_yticks([]);ax.set_title(r['filename'],loc='left',fontsize=10)
axs[-1].set_xlabel('Seconds from file start');fig.suptitle('Provisional signal regions: transitions from 6-s feature contrast; no verse / chorus claims');fig.tight_layout();fig.savefig(ROOT/'output/structure.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(10,4))
for ax,key,title in zip(axs,['spectral_js_distance_bits_sqrt','chroma_cosine'],['Spectral distance (0 = identical distribution)','Pitch-class cosine (1 = identical profile)']):
 mat=np.eye(4) if key=='chroma_cosine' else np.zeros((4,4))
 for p in D['pairs']:i=ord(p['a'])-65;j=ord(p['b'])-65;mat[i,j]=mat[j,i]=p[key]
 im=ax.imshow(mat,cmap='Blues',vmin=0 if key!='chroma_cosine' else .9,vmax=.17 if key!='chroma_cosine' else 1);ax.set_xticks(range(4),['A','B','C','D']);ax.set_yticks(range(4),['A','B','C','D']);ax.set_title(title,fontsize=10)
 for i in range(4):
  for j in range(4):ax.text(j,i,f'{mat[i,j]:.3f}',ha='center',va='center',color='white' if (mat[i,j]>.10 if key!='chroma_cosine' else mat[i,j]>.97) else 'black')
fig.suptitle('Feature similarities; neither measure tests melody, lyrics, genre or musical quality');fig.tight_layout();fig.savefig(ROOT/'output/similarity.png',dpi=170);plt.close(fig)
print('Finished supplemental features')
