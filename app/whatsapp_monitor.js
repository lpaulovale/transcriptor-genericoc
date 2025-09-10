const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const axios = require('axios');
const FormData = require('form-data');

// --- 1. CLIENT INITIALIZATION ---
const client = new Client({
    authStrategy: new LocalAuth({
        clientId: "grupo-monitor"
    }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--single-process',
            '--disable-gpu',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor'
        ]
    }
});

// --- 2. DIRECTORY SETUP ---
const messagesDir = './messages';
const audioDir = './audio_files';
const mediaDir = './media_files';
const visitDocumentsDir = './visit_documents';

// Create all necessary directories
[messagesDir, audioDir, mediaDir, visitDocumentsDir].forEach(dir => {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
});

// --- 3. API CONFIGURATION ---
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

if (!GEMINI_API_KEY) {
    console.error('❌ GEMINI_API_KEY environment variable is required');
    process.exit(1);
}

// --- 4. USER SESSION MANAGEMENT ---
const userSessions = new Map();

const SESSION_STATES = {
    WAITING_PIN: 'waiting_pin',
    AUTHENTICATED: 'authenticated',
    DOCUMENTING_VISIT: 'documenting_visit'
};

// Global variable to store the target group
let targetGroupChat = null;

function getUserSession(userId) {
    if (!userSessions.has(userId)) {
        userSessions.set(userId, {
            state: null,
            pin: null,
            visitDocuments: [],
            visitTexts: []
        });
    }
    return userSessions.get(userId);
}

// --- 5. CLIENT EVENT HANDLERS ---
client.on('qr', (qr) => {
    console.log('Scan the QR code below with your WhatsApp mobile app:');
    qrcode.generate(qr, { small: false });
});

client.on('ready', async () => {
    console.log('✅ WhatsApp interactive bot is ready!');
    console.log('Bot will respond to messages in groups containing "grupo" in their name');
    
    const chats = await client.getChats();
    console.log('\n🔍 Available chats:');
    chats.forEach((chat, index) => {
        console.log(`${index + 1}. ${chat.isGroup ? '[GROUP]' : '[INDIVIDUAL]'} ${chat.name} (ID: ${chat.id._serialized})`);
    });
    
    // Find and store the target group
    targetGroupChat = chats.find(chat => chat.isGroup && chat.name.toLowerCase().includes('grupo'));
    
    if (targetGroupChat) {
        console.log(`\n🎯 Target group found: "${targetGroupChat.name}"`);
        console.log(`🆔 Group ID: ${targetGroupChat.id._serialized}`);
    } else {
        console.log('\n⚠️  No group containing "grupo" found!');
        console.log('Available groups:', chats.filter(c => c.isGroup).map(c => `"${c.name}"`).join(', '));
    }
    
    console.log('\n================================');
    console.log('🤖 Bot is now monitoring messages...');
    console.log('================================\n');
});

client.on('authenticated', () => {
    console.log('✅ Authentication successful!');
});

client.on('auth_failure', (msg) => {
    console.error('❌ Authentication failed:', msg);
});

client.on('disconnected', (reason) => {
    console.log('❌ Client was disconnected:', reason);
});

// --- 6. UTILITY FUNCTIONS ---
function checkFFmpegAvailable() {
    return new Promise((resolve) => {
        exec('ffmpeg -version', (error, stdout, stderr) => {
            resolve(!error);
        });
    });
}

function convertAudioToWav(inputPath, outputPath) {
    return new Promise((resolve) => {
        const command = `ffmpeg -i "${inputPath}" -acodec pcm_s16le -ar 44100 -ac 2 "${outputPath}" -y`;
        
        exec(command, (error, stdout, stderr) => {
            if (error) {
                console.error('FFmpeg conversion error:', error.message);
                resolve(false);
            } else {
                resolve(true);
            }
        });
    });
}

function isValidPin(pin) {
    return /^\d{6}$/.test(pin);
}

// --- 7. API COMMUNICATION ---
async function sendDocumentsToAPI(session, userId) {
    try {
        console.log(`📤 Sending documents to API for user ${userId}`);
        console.log(`📋 Files to send: ${session.visitDocuments.length}`);
        console.log(`📝 Texts to send: ${session.visitTexts.length}`);

        const formData = new FormData();
        
        // Add API key
        formData.append('api_key', GEMINI_API_KEY);
        
        // Add text messages
        if (session.visitTexts.length > 0) {
            session.visitTexts.forEach(text => {
                formData.append('texts', text);
            });
        }
        
        // Add files
        for (const fileName of session.visitDocuments) {
            const filePath = path.join(visitDocumentsDir, fileName);
            if (fs.existsSync(filePath)) {
                const fileBuffer = fs.readFileSync(filePath);
                formData.append('files', fileBuffer, fileName);
                console.log(`📎 Added file: ${fileName}`);
            } else {
                console.warn(`⚠️ File not found: ${filePath}`);
            }
        }

        // Send to API
        const response = await axios.post(`${API_BASE_URL}/extract/visit-report`, formData, {
            headers: {
                ...formData.getHeaders(),
            },
            timeout: 60000, // 60 seconds timeout
        });

        if (response.data.sucesso) {
            console.log('✅ API processing successful');
            return {
                success: true,
                data: response.data.dados
            };
        } else {
            console.error('❌ API processing failed:', response.data.erro);
            return {
                success: false,
                error: response.data.erro
            };
        }

    } catch (error) {
        console.error('❌ Error sending documents to API:', error.message);
        return {
            success: false,
            error: error.message
        };
    }
}

function formatReportForWhatsApp(reportData) {
    let message = '📋 *RELATÓRIO DE VISITA DOMICILIAR*\n\n';
    
    if (reportData.patient_state) {
        message += `👤 *Estado do Paciente:* ${reportData.patient_state}\n\n`;
    }
    
    if (reportData.vitals) {
        message += '🩺 *SINAIS VITAIS:*\n';
        if (reportData.vitals.bp_systolic && reportData.vitals.bp_diastolic) {
            message += `• PA: ${reportData.vitals.bp_systolic}/${reportData.vitals.bp_diastolic} mmHg\n`;
        }
        if (reportData.vitals.hr) {
            message += `• FC: ${reportData.vitals.hr} bpm\n`;
        }
        if (reportData.vitals.temp_c) {
            message += `• Temperatura: ${reportData.vitals.temp_c}°C\n`;
        }
        if (reportData.vitals.spo2) {
            message += `• SpO2: ${reportData.vitals.spo2}%\n`;
        }
        message += '\n';
    }
    
    if (reportData.medications_in_use && reportData.medications_in_use.length > 0) {
        message += '💊 *MEDICAMENTOS EM USO:*\n';
        reportData.medications_in_use.forEach(med => {
            message += `• ${med}\n`;
        });
        message += '\n';
    }
    
    if (reportData.medications_administered && reportData.medications_administered.length > 0) {
        message += '💉 *MEDICAMENTOS ADMINISTRADOS:*\n';
        reportData.medications_administered.forEach(med => {
            message += `• *${med.name || 'N/A'}*\n`;
            if (med.dose) message += `  Dose: ${med.dose}\n`;
            if (med.route) message += `  Via: ${med.route}\n`;
            if (med.time) message += `  Horário: ${med.time}\n`;
            message += '\n';
        });
    }
    
    if (reportData.materials_used && reportData.materials_used.length > 0) {
        message += '🧰 *MATERIAIS UTILIZADOS:*\n';
        reportData.materials_used.forEach(material => {
            message += `• ${material}\n`;
        });
        message += '\n';
    }
    
    if (reportData.interventions && reportData.interventions.length > 0) {
        message += '🔧 *INTERVENÇÕES REALIZADAS:*\n';
        reportData.interventions.forEach(intervention => {
            message += `• ${intervention}\n`;
        });
        message += '\n';
    }
    
    if (reportData.recommendations && reportData.recommendations.length > 0) {
        message += '📝 *RECOMENDAÇÕES:*\n';
        reportData.recommendations.forEach(rec => {
            message += `• ${rec}\n`;
        });
        message += '\n';
    }
    
    if (reportData.observations) {
        message += `💭 *OBSERVAÇÕES:*\n${reportData.observations}\n\n`;
    }
    
    if (reportData.data_processamento) {
        const processedDate = new Date(reportData.data_processamento).toLocaleString('pt-BR');
        message += `⏰ *Processado em:* ${processedDate}`;
    }
    
    return message;
}

// --- 8. MESSAGE PROCESSING AND SAVING ---
async function saveMessageData(message, chat, contact, additionalData = {}) {
    const timestamp = new Date(message.timestamp * 1000);
    
    const messageData = {
        id: message.id.id,
        from: contact.pushname || contact.name || contact.number,
        fromNumber: contact.id.user,
        timestamp: timestamp.toISOString(),
        type: message.type,
        body: message.body,
        groupName: chat.name,
        groupId: chat.id._serialized,
        isOwnMessage: message.fromMe,
        ...additionalData
    };

    // Save to daily JSON log file
    const dateStr = timestamp.toISOString().split('T')[0];
    const logFileName = `messages_${dateStr}.json`;
    const logPath = path.join(messagesDir, logFileName);

    let existingMessages = [];
    if (fs.existsSync(logPath)) {
        try {
            const fileContent = fs.readFileSync(logPath, 'utf8');
            if (fileContent) {
                existingMessages = JSON.parse(fileContent);
            }
        } catch (parseError) {
            console.error(`Error parsing existing messages file:`, parseError);
            existingMessages = [];
        }
    }

    existingMessages.push(messageData);
    fs.writeFileSync(logPath, JSON.stringify(existingMessages, null, 2));
    console.log(`✅ Message logged to: ${logFileName}`);

    return messageData;
}

async function handleMediaMessage(message, session, isVisitDocument = false) {
    let savedFiles = [];
    
    if (message.type === 'ptt' || message.type === 'audio') {
        try {
            const media = await message.downloadMedia();
            if (media) {
                const originalExtension = media.mimetype.split('/')[1] || 'ogg';
                const originalFileName = `audio_${Date.now()}_${message.id.id}.${originalExtension}`;
                const targetDir = isVisitDocument ? visitDocumentsDir : audioDir;
                const originalPath = path.join(targetDir, originalFileName);

                fs.writeFileSync(originalPath, media.data, 'base64');
                savedFiles.push(originalFileName);
                console.log(`✅ Audio saved: ${originalFileName}`);

                // Convert to WAV if FFmpeg is available
                const ffmpegAvailable = await checkFFmpegAvailable();
                if (ffmpegAvailable) {
                    const wavFileName = `audio_${Date.now()}_${message.id.id}.wav`;
                    const wavPath = path.join(targetDir, wavFileName);
                    
                    const converted = await convertAudioToWav(originalPath, wavPath);
                    if (converted) {
                        savedFiles.push(wavFileName);
                        console.log(`✅ Audio converted to WAV: ${wavFileName}`);
                    }
                }

                if (isVisitDocument) {
                    session.visitDocuments.push(...savedFiles);
                }
            }
        } catch (error) {
            console.error('❌ Error downloading audio:', error);
        }
    } else if (message.hasMedia) {
        try {
            const media = await message.downloadMedia();
            if (media && media.mimetype) {
                const extension = media.mimetype.split('/')[1] || 'bin';
                const mediaFileName = `${message.type}_${Date.now()}_${message.id.id}.${extension}`;
                const targetDir = isVisitDocument ? visitDocumentsDir : mediaDir;
                const mediaPath = path.join(targetDir, mediaFileName);

                fs.writeFileSync(mediaPath, media.data, 'base64');
                savedFiles.push(mediaFileName);
                console.log(`✅ Media saved: ${mediaFileName}`);

                if (isVisitDocument) {
                    session.visitDocuments.push(mediaFileName);
                }
            }
        } catch (error) {
            console.error('❌ Error downloading media:', error);
        }
    }

    return savedFiles;
}

// --- 9. BOT CONVERSATION LOGIC ---
async function sendBotMessage(chat, messageText) {
    console.log(`🤖 SENDING: "${messageText}"`);
    
    try {
        // Add a small delay to prevent rapid sending
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Try method 1: Direct chat sendMessage
        const result = await chat.sendMessage(messageText);
        console.log(`✅ Message sent successfully via chat.sendMessage`);
        return result;
    } catch (error1) {
        console.error(`❌ chat.sendMessage failed:`, error1.message);
        
        try {
            // Try method 2: Client sendMessage
            const result = await client.sendMessage(chat.id._serialized, messageText);
            console.log(`✅ Message sent successfully via client.sendMessage`);
            return result;
        } catch (error2) {
            console.error(`❌ client.sendMessage also failed:`, error2.message);
            throw error2;
        }
    }
}

async function handleBotConversation(message, chat, contact) {
    const userId = contact.id.user;
    const session = getUserSession(userId);
    const userMessage = message.body ? message.body.trim() : '';

    console.log(`\n🤖 BOT CONVERSATION START`);
    console.log(`👤 User: ${contact.pushname || contact.number} (${userId})`);
    console.log(`💭 Message: "${userMessage}"`);
    console.log(`📄 Current State: ${session.state || 'NEW_USER'}`);
    console.log(`🔍 Message Type: ${message.type}`);

    // Skip empty messages or non-text messages for conversation logic
    if (!userMessage && message.type === 'chat') {
        console.log(`⚠️ Empty text message, skipping conversation logic`);
        return;
    }

    // For media messages in documentation mode, handle them separately
    if (!userMessage && message.type !== 'chat' && session.state === SESSION_STATES.DOCUMENTING_VISIT) {
        console.log(`🔎 Processing media message in documentation mode`);
        const savedFiles = await handleMediaMessage(message, session, true);
        
        if (savedFiles.length > 0) {
            try {
                await sendBotMessage(chat, `✅ Documento(s) recebido(s) e salvo(s)!\n\nContinue enviando mais documentos ou digite "0" ou "sair" para finalizar.`);
                console.log(`✅ Document received confirmation sent successfully`);
            } catch (error) {
                console.error(`❌ Failed to send document received confirmation:`, error);
            }
        }
        return;
    }

    // Skip if no text message for conversation logic
    if (!userMessage) {
        console.log(`⚠️ No text content for conversation logic, skipping`);
        return;
    }

    // Initial greeting and PIN request
    if (!session.state) {
        session.state = SESSION_STATES.WAITING_PIN;
        console.log(`🎯 SENDING INITIAL GREETING...`);
        
        try {
            await sendBotMessage(chat, 'Olá! Envie o seu PIN para realizar o login.');
            console.log(`✅ Initial greeting sent successfully`);
        } catch (error) {
            console.error(`❌ CRITICAL: Failed to send initial greeting:`, error);
            throw error;
        }
        return;
    }

    // Handle PIN verification
    if (session.state === SESSION_STATES.WAITING_PIN) {
        if (isValidPin(userMessage)) {
            session.pin = userMessage;
            session.state = SESSION_STATES.AUTHENTICATED;
            
            const menuMessage = `PIN aceito! ✅\n\nO que você deseja fazer?\n\n1️⃣ Ver visitas agendadas\n2️⃣ Documentar visita\n\nDigite 1 ou 2 para escolher uma opção.`;
            console.log(`🎯 SENDING MENU...`);
            
            try {
                await sendBotMessage(chat, menuMessage);
                console.log(`✅ Menu sent successfully`);
            } catch (error) {
                console.error(`❌ Failed to send menu:`, error);
                throw error;
            }
        } else {
            console.log(`🎯 SENDING PIN INVALID MESSAGE...`);
            
            try {
                await sendBotMessage(chat, 'PIN inválido. Por favor, envie um PIN de 6 dígitos.');
                console.log(`✅ PIN invalid message sent successfully`);
            } catch (error) {
                console.error(`❌ Failed to send PIN invalid message:`, error);
                throw error;
            }
        }
        return;
    }

    // Handle authenticated user menu
    if (session.state === SESSION_STATES.AUTHENTICATED) {
        if (userMessage === '1') {
            try {
                await sendBotMessage(chat, '📅 Funcionalidade "Ver visitas agendadas" em desenvolvimento.\n\nDigite 2 para documentar visita ou envie um novo PIN para reiniciar.');
                console.log(`✅ Visits menu sent successfully`);
            } catch (error) {
                console.error(`❌ Failed to send visits menu:`, error);
                throw error;
            }
        } else if (userMessage === '2') {
            session.state = SESSION_STATES.DOCUMENTING_VISIT;
            session.visitDocuments = [];
            session.visitTexts = [];
            try {
                await sendBotMessage(chat, '📝 Modo documentação ativado!\n\nAberto a receber os documentos da visita:\n• Envie arquivos, fotos, áudios ou texto escrito\n• Digite "0" ou "sair" quando terminar');
                console.log(`✅ Documentation mode message sent successfully`);
            } catch (error) {
                console.error(`❌ Failed to send documentation mode message:`, error);
                throw error;
            }
        } else if (isValidPin(userMessage)) {
            // Allow user to restart with a new PIN
            session.pin = userMessage;
            session.state = SESSION_STATES.AUTHENTICATED;
            session.visitDocuments = [];
            session.visitTexts = [];
            
            const menuMessage = `PIN aceito! ✅\n\nO que você deseja fazer?\n\n1️⃣ Ver visitas agendadas\n2️⃣ Documentar visita\n\nDigite 1 ou 2 para escolher uma opção.`;
            
            try {
                await sendBotMessage(chat, menuMessage);
                console.log(`✅ Menu sent successfully (restart)`);
            } catch (error) {
                console.error(`❌ Failed to send menu (restart):`, error);
                throw error;
            }
        } else {
            try {
                await sendBotMessage(chat, 'Opção inválida. Digite:\n1️⃣ Ver visitas agendadas\n2️⃣ Documentar visita');
                console.log(`✅ Invalid option message sent successfully`);
            } catch (error) {
                console.error(`❌ Failed to send invalid option message:`, error);
                throw error;
            }
        }
        return;
    }

    // Handle visit documentation
    if (session.state === SESSION_STATES.DOCUMENTING_VISIT) {
        if (userMessage.toLowerCase() === '0' || userMessage.toLowerCase() === 'sair') {
            console.log(`📋 Visit documentation completed for user ${userId}`);
            console.log(`📁 Documents collected: ${session.visitDocuments.length} files`);
            console.log(`📝 Texts collected: ${session.visitTexts.length} texts`);
            
            // Show processing message
            try {
                await sendBotMessage(chat, '⏳ Processando dados com IA...\n\nAguarde enquanto analiso os documentos da visita.');
                console.log(`⏳ Processing message sent successfully`);
            } catch (error) {
                console.error(`❌ Failed to send processing message:`, error);
            }
            
            // Send documents to API and get transcription
            const apiResult = await sendDocumentsToAPI(session, userId);
            
            if (apiResult.success && apiResult.data) {
                // Format and send the report
                const formattedReport = formatReportForWhatsApp(apiResult.data);
                try {
                    await sendBotMessage(chat, formattedReport);
                    await sendBotMessage(chat, '\n✅ Documentação da visita concluída com sucesso!\n\nDigite um novo PIN para iniciar uma nova sessão.');
                    console.log(`✅ Report sent successfully`);
                } catch (error) {
                    console.error(`❌ Failed to send report:`, error);
                    try {
                        await sendBotMessage(chat, '❌ Erro ao enviar relatório. Tente novamente.\n\nDigite um novo PIN para iniciar uma nova sessão.');
                    } catch (fallbackError) {
                        console.error(`❌ Failed to send fallback message:`, fallbackError);
                    }
                }
            } else {
                // API processing failed
                const errorMessage = `❌ Erro ao processar documentos:\n${apiResult.error}\n\nDigite um novo PIN para tentar novamente.`;
                try {
                    await sendBotMessage(chat, errorMessage);
                    console.log(`❌ Error message sent successfully`);
                } catch (error) {
                    console.error(`❌ Failed to send error message:`, error);
                }
            }
            
            // Reset session
            session.state = null;
            session.visitDocuments = [];
            session.visitTexts = [];
            
        } else {
            // Handle document collection (text messages)
            if (message.type === 'chat' && userMessage) {
                const textFileName = `text_${Date.now()}_${message.id.id}.txt`;
                const textPath = path.join(visitDocumentsDir, textFileName);
                fs.writeFileSync(textPath, userMessage, 'utf8');
                session.visitTexts.push(userMessage); // Store text content for API
                console.log(`✅ Text document saved: ${textFileName}`);
                
                try {
                    await sendBotMessage(chat, `✅ Texto recebido e salvo!\n\nContinue enviando mais documentos ou digite "0" ou "sair" para finalizar.`);
                    console.log(`✅ Text received confirmation sent successfully`);
                } catch (error) {
                    console.error(`❌ Failed to send text received confirmation:`, error);
                }
            }
        }
        return;
    }

    console.log(`🤖 BOT CONVERSATION END\n`);
}

// --- 10. MAIN MESSAGE HANDLER ---
async function processMessage(message, source = 'unknown') {
    try {
        console.log(`\n📄 PROCESSING MESSAGE [${source}]`);
        console.log(`📨 Message ID: ${message.id.id}`);
        console.log(`📨 From: ${message.from}`);
        console.log(`📨 FromMe: ${message.fromMe}`);
        console.log(`📨 Type: ${message.type}`);
        console.log(`📨 Body: "${message.body}"`);
        
        const chat = await message.getChat();
        const contact = await message.getContact();

        console.log(`📨 Chat: "${chat.name}" (Group: ${chat.isGroup})`);
        console.log(`📨 Contact: ${contact.pushname || contact.number}`);

        // Only process messages from groups containing "grupo" in their name
        if (!chat.isGroup || !chat.name.toLowerCase().includes('grupo')) {
            console.log(`❌ Message not from target groups - IsGroup: ${chat.isGroup}, ChatName: "${chat.name}"`);
            return false;
        }

        console.log(`✅ Message qualifies for processing!`);

        // Save all messages for logging (both incoming and outgoing)
        let additionalData = {};
        
        if (message.type === 'ptt' || message.type === 'audio' || message.hasMedia) {
            const savedFiles = await handleMediaMessage(message, getUserSession(contact.id.user), false);
            if (savedFiles.length > 0) {
                additionalData.savedFiles = savedFiles;
            }
        }

        await saveMessageData(message, chat, contact, additionalData);

        // CRITICAL: Only handle bot conversation for INCOMING messages (not our own messages)
        if (!message.fromMe) {
            console.log(`🤖 Processing bot conversation for incoming message...`);
            try {
                await handleBotConversation(message, chat, contact);
            } catch (conversationError) {
                console.error(`❌ Error in bot conversation:`, conversationError);
            }
        } else {
            console.log(`⭐️ Skipping bot conversation for own message`);
        }

        return true;

    } catch (error) {
        console.error('❌ Error processing message:', error);
        return false;
    }
}

// --- 11. MESSAGE EVENT HANDLERS ---
client.on('message', async (message) => {
    console.log('\n📨 MESSAGE EVENT TRIGGERED');
    console.log(`FromMe: ${message.fromMe}, From: ${message.from}`);
    
    if (message.from) {
        const processed = await processMessage(message, 'message_event');
        if (!processed) {
            console.log('⚠️  Message was not processed');
        }
    } else {
        console.log('❌ Invalid message (no from field)');
    }
});

client.on('message_create', async (message) => {
    console.log('\n📤 MESSAGE_CREATE EVENT TRIGGERED');
    console.log(`FromMe: ${message.fromMe}, From: ${message.from}`);
    
    // Only log our own messages, don't respond to them
    if (message.from && message.fromMe) {
        const processed = await processMessage(message, 'message_create_event');
        if (!processed) {
            console.log('⚠️  Own message was not processed');
        }
    } else if (!message.fromMe) {
        // This handles the case where message_create fires for incoming messages too
        console.log('🔥 Incoming message via message_create - will be handled by message event');
    } else {
        console.log('❌ Invalid own message (no from field)');
    }
});

// --- 12. INITIALIZATION ---
async function initializeClient() {
    const ffmpegAvailable = await checkFFmpegAvailable();

    if (ffmpegAvailable) {
        console.log('✅ FFmpeg detected. Audio conversion is enabled.');
    } else {
        console.log('⚠️  FFmpeg not found. Audio files will be saved in original format.');
    }

    console.log('🚀 Starting WhatsApp Interactive Bot...');
    console.log(`📡 API Base URL: ${API_BASE_URL}`);
    
    try {
        await client.initialize();
    } catch (error) {
        console.error('❌ Failed to initialize client:', error.message);
        console.log('\n🔧 Troubleshooting suggestions:');
        console.log('1. Install Puppeteer: npm install puppeteer');
        console.log('2. Check your internet connection.');
        console.log('3. Try removing the ".wwebjs_auth" folder to reset the session.');
        process.exit(1);
    }
}

// --- 13. UTILITY FUNCTIONS ---
function searchMessages(criteria) {
    const files = fs.readdirSync(messagesDir).filter(file => file.endsWith('.json'));
    let allMessages = [];

    files.forEach(file => {
        try {
            const filePath = path.join(messagesDir, file);
            const content = fs.readFileSync(filePath, 'utf8');
            if (content) {
                const messages = JSON.parse(content);
                allMessages = allMessages.concat(messages);
            }
        } catch (error) {
            console.error(`Error reading ${file}:`, error);
        }
    });

    if (criteria.date) {
        allMessages = allMessages.filter(msg =>
            msg.timestamp.startsWith(criteria.date)
        );
    }

    if (criteria.sender) {
        allMessages = allMessages.filter(msg =>
            (msg.from && msg.from.toLowerCase().includes(criteria.sender.toLowerCase())) ||
            (msg.fromNumber && msg.fromNumber.includes(criteria.sender))
        );
    }

    return allMessages;
}

function getMessageStats() {
    const files = fs.readdirSync(messagesDir).filter(file => file.endsWith('.json'));
    let totalMessages = 0;
    let audioMessages = 0;
    let mediaMessages = 0;
    let ownMessages = 0;

    files.forEach(file => {
        try {
            const filePath = path.join(messagesDir, file);
            const content = fs.readFileSync(filePath, 'utf8');
            if (content) {
                const messages = JSON.parse(content);
                totalMessages += messages.length;
                audioMessages += messages.filter(m => m.type === 'ptt' || m.type === 'audio').length;
                mediaMessages += messages.filter(m => m.hasMedia).length;
                ownMessages += messages.filter(m => m.isOwnMessage).length;
            }
        } catch (error) {
            console.error(`Error reading ${file} for stats:`, error);
        }
    });

    return {
        totalMessages,
        audioMessages,
        mediaMessages,
        ownMessages,
        othersMessages: totalMessages - ownMessages
    };
}

// Start the client
initializeClient();

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\nShutting down gracefully...');
    await client.destroy();
    process.exit(0);
});

// Export functions
module.exports = { searchMessages, getMessageStats };