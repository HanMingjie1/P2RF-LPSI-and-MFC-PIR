#include <iostream>
#include <string>
#include <cstdlib>
#include <cstring>
#include <array>
#include <vector>
#include <sstream>
#include <iomanip>
#include "Insection.h"
#include "psi/client.h"
#include "psi/common/stopwatch.h"
#include "psi/common/thread_pool_mgr.h"
#include <fstream>
#include <chrono>

void printHelp() {
    std::cout << "Usage: Client_cli " << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -h, --help     Display this help message" << std::endl;
}

std::vector<std::vector<uint8_t>> readReceivershareBytes() {
    std::vector<std::vector<uint8_t>> receivershare_bytes;
    std::string filename = "/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/receivershare_binary_with_bytes.txt";
    
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cout << "Warning: Cannot open " << filename << std::endl;
        return receivershare_bytes;
    }
    
    std::string line;
    while (std::getline(file, line)) {
        if (line.empty()) continue;
        
        // 解析格式: "二进制字符串 十六进制字节"
        std::istringstream iss(line);
        std::string binary_str, hex_str;
        iss >> binary_str >> hex_str;
        
        if (!hex_str.empty()) {
            // 将十六进制字符串转换为字节数组
            std::vector<uint8_t> bytes;
            for (size_t i = 0; i < hex_str.length(); i += 2) {
                std::string byte_str = hex_str.substr(i, 2);
                uint8_t byte_val = static_cast<uint8_t>(std::stoul(byte_str, nullptr, 16));
                bytes.push_back(byte_val);
            }
            receivershare_bytes.push_back(bytes);
        }
    }
    
    file.close();
    std::cout << "Loaded " << receivershare_bytes.size() << " lines from receivershare_binary_with_bytes.txt" << std::endl;
    return receivershare_bytes;
}
struct clientparams{
    size_t threads;
    size_t setsize;
    size_t logsetsize;
    size_t inssize=1;
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
    auto t_data_gen_start = std::chrono::steady_clock::now();
    std::vector<PSI::Item> ReceiverSet;
    
    // 存储所有数据用于按列输出
    std::vector<std::array<uint8_t, 16>> random_ids_16;
    std::vector<std::vector<uint8_t>> share_bytes;
    
    // 打开输出文件
    std::ofstream output_file("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/client_generated_data.txt");
    if (!output_file.is_open()) {
        std::cout << "Warning: Cannot open output file for writing" << std::endl;
    }
    
    // 生成数据不计入offline
    for(size_t idx = 0; idx < cmdparams.setsize; idx++){
        // 使用动态的Item_byte_size
        std::array<uint8_t, PSI::Item_byte_size> item_data;
        RAND_bytes(item_data.data(), PSI::Item_byte_size);
        ReceiverSet.emplace_back(item_data);
        
        // 分离16字节随机ID和byte_count字节share
        std::array<uint8_t, 16> random_id_16;
        std::memcpy(random_id_16.data(), item_data.data(), 16);
        random_ids_16.push_back(random_id_16);
        
        if(PSI::Item_byte_size > 16){
            size_t byte_count = PSI::Item_byte_size - 16;
            std::vector<uint8_t> share_data(byte_count);
            std::memcpy(share_data.data(), item_data.data() + 16, byte_count);
            share_bytes.push_back(share_data);
        } else {
            share_bytes.push_back(std::vector<uint8_t>());
        }
    }
    
    // 读取receivershare字节数据
    auto receivershare_bytes = readReceivershareBytes();
    
    // 处理交集替换
    for(size_t idx = 0; idx <cmdparams.inssize; idx++){
        if(idx < ReceiverSet.size()){
            // 将insection数据转换为Item_byte_size格式
            std::array<uint8_t, PSI::Item_byte_size> item_data;
            // 将insection的16字节数据复制到item_data的前16字节
            std::memcpy(item_data.data(), &insection[idx], 16);
            
            // 如果Item_byte_size > 16，用receivershare数据填充剩余字节
            if(PSI::Item_byte_size > 16){
                size_t remaining_bytes = PSI::Item_byte_size - 16;
                
                if(idx < receivershare_bytes.size() && receivershare_bytes[idx].size() >= remaining_bytes){
                    // 使用receivershare数据填充剩余字节
                    std::memcpy(item_data.data() + 16, receivershare_bytes[idx].data(), remaining_bytes);
                    std::cout << "Replaced bytes for intersection item " << idx << " with receivershare data" << std::endl;
                } else {
                    // 如果receivershare数据不足，用随机数据填充
                    RAND_bytes(item_data.data() + 16, remaining_bytes);
                    std::cout << "Warning: Not enough receivershare data for item " << idx << ", using random data" << std::endl;
                }
            }
            ReceiverSet[idx] = PSI::Item(item_data);
            
            // 更新存储的数据（交集替换后的数据）
            std::memcpy(random_ids_16[idx].data(), item_data.data(), 16);
            if(PSI::Item_byte_size > 16){
                size_t byte_count = PSI::Item_byte_size - 16;
                share_bytes[idx].resize(byte_count);
                std::memcpy(share_bytes[idx].data(), item_data.data() + 16, byte_count);
            }
        }
    }
    
    // 按列输出ID数据到文件（与Server相同规则）
    if (output_file.is_open()) {
        // 输出列标题
        output_file << "16字节随机ID(替换交集后)+share" << std::endl;
        
        // 按行输出数据
        for(size_t idx = 0; idx < cmdparams.setsize; idx++){
            // 第一列：16字节随机ID（替换交集后的）+ share
            for (size_t i = 0; i < 16; i++) {
                output_file << std::hex << std::setfill('0') << std::setw(2) << static_cast<int>(random_ids_16[idx][i]);
            }
            // 添加share数据
            if(!share_bytes[idx].empty()){
                for (size_t i = 0; i < share_bytes[idx].size(); i++) {
                    output_file << std::hex << std::setfill('0') << std::setw(2) << static_cast<int>(share_bytes[idx][i]);
                }
            }
            output_file << std::dec << std::endl;
        }
        
        output_file.close();
        std::cout << "Client generated data saved to: client_generated_data.txt" << std::endl;
    }
    auto t_data_gen_end = std::chrono::steady_clock::now();
    std::cout << "Prepare TestData Finish" << std::endl;
    PSI::StopWatch clientclocks("client");
    PSI::ThreadPoolMgr::SetThreadCount(cmdparams.threads);
    clientclocks.setpoint("start");
    droidCrypto::CSocketChannel chanc("127.0.0.1", 8000, false);
    clientclocks.setpoint("Network start");
    auto t_online_start = std::chrono::steady_clock::now();
    PSI::Client::PSIClient client(cmdparams.setsize,chanc);
    clientclocks.setpoint("start");
    client.DHBased_SIMDDPF_PSI_start("127.0.0.1:51000","127.0.0.1:51001",ReceiverSet);
    auto t_online_end = std::chrono::steady_clock::now();
    clientclocks.setpoint("ALL Finish");
    std::cout << "------------------- ALL Client Finish ---------------------" << std::endl;
    clientclocks.printTimePointRecord();
    auto t_all_end = std::chrono::steady_clock::now();
    double data_gen = std::chrono::duration<double, std::milli>(t_data_gen_end - t_data_gen_start).count();
    double online = std::chrono::duration<double, std::milli>(t_online_end - t_online_start).count();
    double offline = std::chrono::duration<double, std::milli>(t_online_start - t_data_gen_end).count();
    std::ofstream fout("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/cli/time.txt", std::ios::app);
    fout << "Client data_gen: " << data_gen << " ms" << std::endl;
    fout << "Client online: " << online << " ms, offline: " << offline << " ms" << std::endl;
    // 写出本角色的在线/离线时间供汇总
    {
        std::ofstream role_file("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/role_times_client.txt", std::ios::trunc);
        if (role_file.is_open()) {
            role_file << online << "\n" << offline << "\n";
        }
    }
    
    // 输出详细性能数据到结果文件
    std::ofstream performance_file("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/intersection_results.txt", std::ios::app);
    if (performance_file.is_open()) {
        performance_file << std::endl << "=== Performance Data ===" << std::endl;
        performance_file << "Data Generation Time: " << data_gen << " ms" << std::endl;
        performance_file << "Online Time: " << online << " ms" << std::endl;
        performance_file << "Offline Time: " << offline << " ms" << std::endl;
        performance_file << "Total Time: " << (data_gen + online + offline) << " ms" << std::endl;
        // 汇总三端 Online/Offline 时间并写入同一块
        {
            double sum_online = online, sum_offline = offline;
            auto read_role = [&](const char* p){
                std::ifstream rf(p);
                if (!rf.is_open()) return; 
                std::string s_on, s_off; 
                if (std::getline(rf, s_on)) { try { sum_online += std::stod(s_on); } catch(...){} }
                if (std::getline(rf, s_off)) { try { sum_offline += std::stod(s_off); } catch(...){} }
            };
            read_role("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/role_times_server.txt");
            read_role("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/role_times_aid.txt");
            performance_file << "Sum Online Time: " << sum_online << " ms" << std::endl;
            performance_file << "Sum Offline Time: " << sum_offline << " ms" << std::endl;
        }
        // 读取服务端写入的MB统计并写入同一块
        {
            std::ifstream mb_file("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/mb_stats.txt");
            if (mb_file.is_open()) {
                std::string offline_mb, online_mb;
                std::getline(mb_file, offline_mb);
                std::getline(mb_file, online_mb);
                if(!offline_mb.empty()) performance_file << "Offline Data: " << offline_mb << " MB" << std::endl;
                if(!online_mb.empty())  performance_file << "Online  Data: " << online_mb  << " MB" << std::endl;
            }
        }
        // 读取ss3r.py记录的仅转换耗时并写入同一块
        {
            std::ifstream conv_file("/home/hmj/P2FRLPSI/DPFPSI-main/DPFPSI/conv_time_ms.txt");
            if (conv_file.is_open()) {
                std::string conv_ms;
                std::getline(conv_file, conv_ms);
                if(!conv_ms.empty()) performance_file << "Data Conversion Time (ss3r): " << conv_ms << " ms" << std::endl;
            }
        }
        performance_file << "=================================" << std::endl;
        performance_file.close();
    }
    return 0;
}

