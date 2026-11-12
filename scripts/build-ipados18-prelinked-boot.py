#!/usr/bin/env python3
"""Prelink matching 22H374 kexts and package them with Diting DarwinBoot24."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'kits/NativePrelink'))
import diting_paths
from emit_prelink import emit,COALESCED
from native_prelink import arm64_image,macho,plan
from diting_rootful_policy import apply as apply_rootful_policy

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--artifact-dir',type=Path,default=ROOT/'out/ipados18/kernel')
 p.add_argument('--original',type=Path,default=ROOT/'apple/ipados18-22H374/components/kernelcache.release.ipad7c.decompressed/kernelcache.release.ipad7c.decompressed')
 p.add_argument('--volume-layout',type=Path,default=diting_paths.volume_layout())
 p.add_argument('--output-dir',type=Path,required=True)
 p.add_argument('--cpus',type=int,choices=range(1,9),default=8,
                help='actual Diting CPU nodes; use --cpus 1 for isolated bring-up')
 p.add_argument('--window-size',type=lambda s:int(s,0),default=0x100000000)
 p.add_argument('--kernel-arg',action='append',default=[])
 a=p.parse_args()
 if (a.output_dir/'diting-xnu-initial.img').exists():raise SystemExit('Existing boot image retained; choose another --output-dir before prelinking')
 a.output_dir.mkdir(parents=True,exist_ok=True)
 report=json.loads((a.artifact_dir/'DITING_BUILD_RESULT.json').read_text())
 if not report['build_complete'] or report['profile']!='Diting-iPadOS18-22H374-Darwin24':raise SystemExit('A completed Darwin 24 build is required')
 active=Path(report['tree']).parent/'DITING_BUILD_RESULT.json'
 if active.exists():
  current=json.loads(active.read_text())
  if not current.get('build_complete') or current.get('log')!=report.get('log'):raise SystemExit('Kernel build/export still pending; package after the current build completes')
 native=(a.artifact_dir/'mach.development.diting').read_bytes();original=arm64_image(a.original.read_bytes());m=macho(original)
 bindings=json.loads((ROOT/'mac-build/native-ufs/bindings.json').read_text())
 if bindings['build']!='22H374':raise SystemExit('Storage imports belong to another restore')
 base=min(s['va'] for s in m['segments'] if s['name'] in COALESCED and s['size']);slide=int(bindings['fixed_prelink_base'],16)-base
 roots=['com.apple.kec.corecrypto','com.apple.kec.pthread','com.apple.filesystems.apfs','com.apple.kec.Compression','com.apple.AppleFSCompression.AppleFSCompressionTypeZlib']
 library={'com.apple.driver.AppleARMWatchdogTimer','com.apple.driver.AppleARMPlatform','com.apple.driver.ApplePMGR','com.apple.driver.AppleEffaceableStorage','com.apple.driver.AppleMobileFileIntegrity'}
 gpu=report['settings'].get('XNU_DITING_ADRENO_PLATFORM')=='1'
 if gpu:
  roots.append('com.apple.iokit.IOGPUFamily')
  library.update({'com.apple.iokit.IOGPUFamily','com.apple.iokit.IOSurface',
                  'com.apple.iokit.IOReportFamily','com.apple.iokit.IOSlowAdaptiveClockingFamily'})
 closure=plan(native,original,roots,slide,verify_images=False)
 library&=set(closure['components'])
 candidate,selection=emit(native,original,roots,slide,verify_images=False,library_only_components=library)
 # A single board-owned root-upgrade call is adapted after ordinary prelink.
 # The native helper retains the stock policy unless explicitly requested.
 candidate,selection['diting_rootful_policy']=apply_rootful_policy(candidate,native,original,slide,selection['components'])
 kernel=a.output_dir/'kernel-ipados18.macho';kernel.write_bytes(candidate)
 (a.output_dir/'prelink.json').write_text(json.dumps(selection,indent=2)+'\n')
 report['base_kernel']=report['kernel'];report['kernel']={'path':str(kernel),'bytes':len(candidate)};report['prelink']={'components':selection['components'],'library_only_components':selection['library_only_components']};report['image_verification']='skipped by request'
 result=a.output_dir/'DITING_BUILD_RESULT.json';result.write_text(json.dumps(report,indent=2)+'\n')
 layout=json.loads(a.volume_layout.read_text())
 opts=['diting_allow_unauthenticated_root=1','cs_enforcement_disable=1','cs_library_val_enable=0','amfi_get_out_of_my_way=1','-apfs_shared_datavolume','debug=0x14e','serial=0','diting_disable_swap=1','diting_skip_setup=1','diting_ufs_readwrite=1','ignition_level=1','dyld_flags=0x8','launchd_rd=md0','diting_init_trace=1','applog=1','applog_name=launchd,backboardd,SpringBoard,containermanagerd,lsd,runningboardd,logd_helper,powerd','diting_software_keybag=1','diting_display=1','diting_software_ui=1','diting_ui_software=1','diting_touch=1','diting_buttons=1','diting_init_path=/diting/init','diting_build=ipados18-22H374','epoch='+str(int(time.time()))]
 # Keep real, non-boost SM8475 EPSS requests at each domain's allowed maximum.
 # Firmware/LMh still owns actual voltage and thermal frequency limits.
 opts+=['diting_cpu_policy=2']
 # The existing CPU scanout scaler divides independent rows among workers.
 # Leave CPU time for the software compositor and stock service startup.
 if gpu:
  opts=[x for x in opts if x not in ('diting_ui_software=1','diting_software_ui=1')]
  opts+=['diting_ui_software=0','diting_software_ui=0','diting_adreno_start=1','diting_metal=1',
         'diting_gpu_scanout=1','diting_gpu_pool_mib=256','diting_metal_global=1',
         'diting_gpu_pwrlevel=0']
 # PCM stays optional and publishes only after the real APM/amp/DMA route
 # is ready. Do not silently disable it in an otherwise audio-enabled build.
 # Select peripheral workers from the compiled configuration. Keep the
 # wallpaper policy independent of optional network/audio support.
 if report['settings'].get('XNU_DITING_POWER')=='1':opts+=['diting_adsp=2','diting_audio=2']
 if report['settings'].get('XNU_DITING_WIFI')=='1':opts+=['diting_wifi=1']
 opts+=['diting_ram_banks=1','launchd_unsecure_cache=1','diting_poster_snapshot=1',f'fb_threads={min(a.cpus,4)}']
 if report['settings'].get('XNU_DITING_BACKLIGHT')=='1':opts+=['diting_backlight=1']
 # PE_parse_boot_argn can select the first duplicate. Apply command-line
 # overrides before packaging so there is exactly one value per named key.
 for value in a.kernel_arg:
  for item in value.split():
   key=item.split('=',1)[0]
   opts=[old for old in opts if old.split('=',1)[0]!=key]
   opts.append(item)
 cmd=[sys.executable,str(ROOT/'scripts/build-ipados18-bootimg-local.py'),'--kernel',str(kernel),'--result',str(result),'--output-dir',str(a.output_dir),'--loader',str(ROOT/'mac-build/darwinboot24/DarwinBoot24.efi'),'--cpus',str(a.cpus),'--fat-mib','96','--window-size',hex(a.window_size),'--ufs','--root-match-volume-uuid',layout['os']['uuid'],'--development-debug','--verbose-console','--skip-image-verification']
 auth=ROOT/'out/ipados18/system-volume-auth-blob.bin'
 if auth.is_file():
  cmd+=['--system-volume-auth-blob',str(auth)]
  auth_record={'packaged':True,'path':str(auth)}
 else:
  auth_record={'packaged':False,'path':str(auth),
               'reason':'system-volume auth blob is absent; the root-hash payload was not packaged'}
  print(auth_record['reason'],file=sys.stderr)
 (a.output_dir/'system-volume-auth-blob.json').write_text(json.dumps(auth_record,indent=2)+'\n')
 cmd+=['--kernel-arg='+v for v in opts]
 env=dict(os.environ)
 if report.get('schema_version')==2:
  hardware=Path(report['hardware_dtb'])
  if not hardware.is_file():raise RuntimeError('Compiled format2 hardware DTB required')
  env['DITING_HARDWARE_DTB']=str(hardware)
 subprocess.run(cmd,check=True,env=env)
if __name__=='__main__':main()
