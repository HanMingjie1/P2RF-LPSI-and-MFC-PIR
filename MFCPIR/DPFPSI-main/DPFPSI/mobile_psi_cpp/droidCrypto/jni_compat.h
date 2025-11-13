#pragma once

// JNI compatibility definitions for non-Android builds
#ifndef JNIEXPORT
#define JNIEXPORT
#endif

#ifndef JNICALL
#define JNICALL
#endif

// Forward declarations for JNI types
typedef void* JNIEnv;
typedef void* jclass;
typedef void* jobject;
typedef void* jmethodID;
typedef void* jfieldID;
typedef void* jstring;
typedef void* jarray;
typedef void* jbyteArray;
typedef void* jintArray;
typedef void* jlongArray;
typedef void* jfloatArray;
typedef void* jdoubleArray;
typedef void* jbooleanArray;
typedef void* jcharArray;
typedef void* jshortArray;

typedef int jint;
typedef long jlong;
typedef float jfloat;
typedef double jdouble;
typedef unsigned char jboolean;
typedef unsigned short jchar;
typedef signed char jbyte;
typedef short jshort;
