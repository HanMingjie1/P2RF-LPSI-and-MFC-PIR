#include <iostream>
#include <string>
#include <cstdlib>
#include "Insection.h"
#include "psi/server.h"
#include "psi/common/stopwatch.h"
#include "psi/common/thread_pool_mgr.h"
#include <fstream>
#include <chrono>
#include <vector>
#include <map>

void printHelp() {
    std::cout << "Usage: Server_cli " << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -h, --help     Display this help message" << std::endl;
    std::cout << "  -t, --threads  Number of threads" << std::endl;
    std::cout << "  -l, --log      Log set size (2^log)" << std::endl;
    std::cout << "  -i, --ins      Intersection size" << std::endl;
}
struct serverparams{
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
    std::cout << "Client Set size: " << cmdparams.setsize << "(2^"<< cmdparams.logsetsize << ")" << std::endl;
    std::cout << "Insection Size: " << cmdparams.inssize << std::endl;
    return 0;
}

int main(int argc, char* argv[]) {
    auto t_all_start = std::chrono::steady_clock::now();
    if(PerfromCMD(argc,argv))
        return 1;
    
    std::cout << "=== 简化DPFPSI Server - 生成随机数据和Label ===" << std::endl;
    std::cout << "线程数: " << cmdparams.threads << std::endl;
    std::cout << "数据集大小: " << cmdparams.setsize << "(2^" << cmdparams.logsetsize << ")" << std::endl;
    std::cout << "交集大小: " << cmdparams.inssize << std::endl;
    
    // 生成随机数据和对应的label
    auto t_data_gen_start = std::chrono::steady_clock::now();
    std::vector<PSI::Item> ServerSet;
    std::vector<PSI::Label> LabelSet;
    std::map<uint64_t, PSI::Label> labelMap; // 用于快速查找label
    
    for(size_t idx = 0; idx < cmdparams.setsize; idx++){
        uint64_t temp[2];
        RAND_bytes((uint8_t*)temp, 16);
        ServerSet.emplace_back(temp[0], temp[1]);
        
        // 生成对应的label
        if(PSI::Label_byte_size > 0){
            RAND_bytes((uint8_t*)temp, PSI::Label_byte_size);
            PSI::Label label = gsl::make_span((uint8_t*)temp, PSI::Label_byte_size);
            LabelSet.emplace_back(label);
            // 使用item的第一个元素作为key存储label
            labelMap[temp[0]] = label;
        }
    }
    
    // 设置交集数据
    for(size_t idx = 0; idx < cmdparams.inssize; idx++){
        if(idx < ServerSet.size()){
            ServerSet[idx] = PSI::Item(insection[idx], insection[idx+256]); 
        }
    }
    
    auto t_data_gen_end = std::chrono::steady_clock::now();
    std::cout << "数据生成完成，共生成 " << ServerSet.size() << " 个数据项和对应的label" << std::endl;
    
    // 输出Server生成的随机数据到文件
    std::ofstream serverDataFile("/home/hmj/MFCPIR/DPFPSI-main/DPFPSI/cli/server_data.txt");
    serverDataFile << "=== Server生成的随机数据 ===" << std::endl;
    serverDataFile << "数据集大小: " << ServerSet.size() << std::endl;
    serverDataFile << "生成时间: " << std::chrono::duration<double, std::milli>(t_data_gen_end - t_data_gen_start).count() << " ms" << std::endl;
    serverDataFile << "----------------------------------------" << std::endl;
    
    for(size_t i = 0; i < ServerSet.size(); i++) {
        serverDataFile << "数据项[" << i << "]: ";
        // 输出Item的内容（需要根据实际的数据结构调整）
        serverDataFile << "Item[" << i << "]";
        if(i < LabelSet.size()) {
            serverDataFile << " -> Label: ";
            // 输出Label的内容（需要根据实际的数据结构调整）
            serverDataFile << "Label[" << i << "]";
        }
        serverDataFile << std::endl;
    }
    serverDataFile.close();
    std::cout << "Server数据已保存到 server_data.txt" << std::endl;
    
    // 启动网络服务，等待Client请求特定行号的label
    PSI::StopWatch serverclocks("server");
    PSI::ThreadPoolMgr::SetThreadCount(cmdparams.threads);
    serverclocks.setpoint("start");
    
    droidCrypto::CSocketChannel chans("127.0.0.1", 8000, true);
    serverclocks.setpoint("Network start");
    
    auto t_online_start = std::chrono::steady_clock::now();
    
    // 简化的Server：只处理DPF请求，返回对应行号的label
    std::cout << "等待Client连接..." << std::endl;
    
    // 这里应该实现简化的DPF协议，接收Client的Q行号请求，返回对应label
    // 为了简化，我们直接使用原有的PSI Server框架
    PSI::Server::PSIServer server(cmdparams.setsize, chans);
    serverclocks.setpoint("Server initialized");
    
    // 使用简化的DPF协议
    server.DHBased_SIMDDPF_PSI_start("127.0.0.1:50000", "127.0.0.1:50002", ServerSet, LabelSet);
    
    auto t_online_end = std::chrono::steady_clock::now();
    serverclocks.setpoint("ALL Finish");
    
    std::cout << "------------------- Server处理完成 ---------------------" << std::endl;
    serverclocks.printTimePointRecord();
    
    auto t_all_end = std::chrono::steady_clock::now();
    double data_gen = std::chrono::duration<double, std::milli>(t_data_gen_end - t_data_gen_start).count();
    double online = std::chrono::duration<double, std::milli>(t_online_end - t_online_start).count();
    double total = std::chrono::duration<double, std::milli>(t_all_end - t_all_start).count();
    
    std::ofstream fout("/home/hmj/MFCPIR/DPFPSI-main/DPFPSI/cli/time.txt", std::ios::app);
    fout << "=== 简化DPFPSI Server ===" << std::endl;
    fout << "数据生成时间: " << data_gen << " ms" << std::endl;
    fout << "在线处理时间: " << online << " ms" << std::endl;
    fout << "总时间: " << total << " ms" << std::endl;
    fout << "数据集大小: " << cmdparams.setsize << std::endl;
    fout << "----------------------------------------" << std::endl;
    
    return 0;
}
