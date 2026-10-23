from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import subprocess
O=Path(__file__).resolve().parent.parent/'deliverables/背景与图示修订版/figures'
font=FontProperties(fname=subprocess.check_output(['fc-match','SimSun','-f','%{file}']).decode())
plt.rcParams.update({'svg.fonttype':'none','text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black'})
fig,ax=plt.subplots(figsize=(12,6.5));fig.subplots_adjust(left=.29,right=.9,top=.82,bottom=.18)
vals=[.913956834532374,.608192876435375,.35]
ax.barh([2,1,0],vals,height=.46,color=['#76899E','#B6A06D','#C4C6C6'])
ax.set_yticks([2,1,0],['独立答对','提示后答对','看过完整答案'],fontproperties=font,fontsize=20)
ax.set_xlim(0,1);ax.set_xticks([0,.25,.5,.75,1]);ax.tick_params(axis='x',labelsize=15);ax.tick_params(axis='y',length=0,pad=18)
for y,v in zip([2,1,0],vals):ax.text(v+.015,y,f'{v:.3f}',va='center',fontsize=18,color='black')
ax.set_xlabel('掌握估计值',fontproperties=font,fontsize=19,labelpad=15)
ax.set_title('相同起点：0.35',fontproperties=font,fontsize=24,pad=25,loc='left')
for side in ['top','right','left']:ax.spines[side].set_visible(False)
ax.spines['bottom'].set_color('#999999');ax.set_axisbelow(True);ax.grid(axis='x',color='#E6E6E6',linewidth=.6)
fig.savefig(O/'05.png',dpi=250,facecolor='white');fig.savefig(O/'05.svg',facecolor='white')
