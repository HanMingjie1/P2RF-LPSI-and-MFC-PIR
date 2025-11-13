#include <iostream>
#include <string>
#include <cstdlib>
#include "Insection.h"
#include "psi/aid_server.h"
#include "psi/common/stopwatch.h"
#include "psi/common/thread_pool_mgr.h"
#include <fstream>
#include <chrono>
#include <vector>

void printHelp() {
    std::cout << "Usage: AidServer_cli " << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -h, --help     Display this help message" << std::endl;
    std::cout << "  -t, --threads  Number of threads" << std::endl;
    std::cout << "  -l, --log      Log set size (2^log)" << std::endl;
    std::cout << "  -i, --ins      Intersection size" << std::endl;
}
struct aidserverparams{
    size_t threads = 4;
    size_t setsize = 1024;
    size_t logsetsize = 10;
    size_t inssize = 1;
}cmdparams;

int PerfromCMD(int argc, char* argv[]){
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            printHelp();
            return 0;
        } else if (arg == "-t" || arg == "--threads") {
            if (i + 1 < argc) {
                cmdparams.threads = std::atoi(argv[i + 1]);
                ++i;
            } else {
                std::cerr << "Error: No number provided after " << arg << std::endl;
                return 1;
            }
        } else if (arg == "-l" || arg == "--log"){
            if (i + 1 < argc) {
                cmdparams.logsetsize =  std::atoi(argv[i + 1]);
                cmdparams.setsize = 1 << cmdparams.logsetsize;
                ++i;
            } else {
                std::cerr << "Error: No number provided after " << arg << std::endl;
                return 1;
            }
        } else if (arg == "-i" || arg == "--ins"){
            if (i + 1 < argc) {
                cmdparams.inssize = std::atoi(argv[i + 1]);
                ++i;
            } else {
                std::cerr << "Error: No number provided after " << arg << std::endl;
                return 1;
            }
        }
        else {
            printHelp();
            std::cerr << "Error: Unknown option " << arg << std::endl;
            return 1;
        }
    }

    std::cout << "threads: " << cmdparams.threads << std::endl;
    std::cout << "AidServer Set size: " << cmdparams.setsize << "(2^"<< cmdparams.logsetsize << ")" << std::endl;
    std::cout << "Insection Size: " << cmdparams.inssize << std::endl;
    return 0;
}

int main(int argc, char* argv[]) {
    auto t_all_start = std::chrono::steady_clock::now();
    if(PerfromCMD(argc,argv))
        return 1;
    
    std::cout << "=== 简化DPFPSI AidServer - 辅助实现DPF过程 ===" << std::endl;
    std::cout << "线程数: " << cmdparams.threads << std::endl;
    std::cout << "数据集大小: " << cmdparams.setsize << "(2^" << cmdparams.logsetsize << ")" << std::endl;
    std::cout << "交集大小: " << cmdparams.inssize << std::endl;
    
    std::cout << "AidServer准备就绪，等待辅助DPF协议执行..." << std::endl;
    
    PSI::StopWatch aidserverclocks("aidserver");
    PSI::ThreadPoolMgr::SetThreadCount(cmdparams.threads);
    aidserverclocks.setpoint("start");
    
    auto t_online_start = std::chrono::steady_clock::now();
    
    // 简化的AidServer：辅助实现DPF过程
    PSI::AidServer::AidServer aidserver;
    aidserverclocks.setpoint("AidServer initialized");
    
    std::cout << "AidServer开始辅助DPF协议执行..." << std::endl;
    
    // 使用简化的DPF协议，辅助Client和Server之间的通信
    aidserver.DHBased_SIMDDPF_PSI_start("127.0.0.1:50002", "127.0.0.1:50001");
    
    auto t_online_end = std::chrono::steady_clock::now();
    aidserverclocks.setpoint("ALL Finish");
    
    std::cout << "------------------- AidServer处理完成 ---------------------" << std::endl;
    std::cout << "AidServer成功辅助完成了DPF协议" << std::endl;
    aidserverclocks.printTimePointRecord();
    
    auto t_all_end = std::chrono::steady_clock::now();
    double online = std::chrono::duration<double, std::milli>(t_online_end - t_online_start).count();
    double total = std::chrono::duration<double, std::milli>(t_all_end - t_all_start).count();
    
    std::ofstream fout("/home/hmj/MFCPIR/DPFPSI-main/DPFPSI/cli/time.txt", std::ios::app);
    fout << "=== 简化DPFPSI AidServer ===" << std::endl;
    fout << "在线处理时间: " << online << " ms" << std::endl;
    fout << "总时间: " << total << " ms" << std::endl;
    fout << "辅助协议: DPF" << std::endl;
    fout << "----------------------------------------" << std::endl;
    
    return 0;
}
